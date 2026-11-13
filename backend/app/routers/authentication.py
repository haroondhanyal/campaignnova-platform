"""Cookie-based local authentication, account recovery, and department access."""
import base64
import hashlib
import hmac
import os
import re
import secrets
import smtplib
import ssl
import time
from email.message import EmailMessage
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import Response as RawResponse
from pydantic import BaseModel, Field, field_validator

from .. import database
from ..services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["authentication"])
SESSION_COOKIE = "campaignnova_session"
SESSION_HOURS = 12
RESET_MINUTES = 30
DEPARTMENTS = (
    "Administration", "Marketing", "Commercial", "CVM", "Segments", "Customer Care",
    "Retail Sales", "Digital Services", "Business Development", "Business Operations",
    "Product & Services", "Sales", "Customer Success", "Operations", "Carrier & International Wholesale",
    "Campaign Operations", "Data & Analytics", "Engineering", "Technology & IT", "Finance",
    "Human Resources", "People & Organization", "Legal & Regulatory",
)
ROLES = (
    "Super Admin", "Organization Admin", "Admin", "Department Manager", "Campaign Manager",
    "CVM Manager", "Segment Analyst", "Customer Care Agent", "Commercial Analyst",
    "Campaign Agent", "Agent", "Approver", "Data Analyst", "Integration Admin", "Viewer",
)
ADMIN_ROLES = {"Super Admin", "Organization Admin", "Admin"}
CONSENT_MANAGEMENT_ROLES = ADMIN_ROLES | {"Department Manager", "CVM Manager"}
READ_ONLY_ROLES = {"Segment Analyst", "Customer Care Agent", "Commercial Analyst", "Data Analyst", "Viewer"}
ROLE_DEPARTMENTS = {
    "Super Admin": {"Administration"}, "Organization Admin": {"Administration"}, "Admin": {"Administration"},
    "Department Manager": set(DEPARTMENTS) - {"Administration"},
    "Campaign Manager": {"Marketing", "Campaign Operations", "Business Operations", "Digital Services"},
    "CVM Manager": {"CVM"}, "Segment Analyst": {"Segments"},
    "Customer Care Agent": {"Customer Care"}, "Commercial Analyst": {"Commercial"},
    "Campaign Agent": {"Marketing", "Commercial", "CVM", "Campaign Operations", "Business Operations", "Retail Sales", "Digital Services", "Product & Services", "Operations"},
    "Agent": set(DEPARTMENTS) - {"Administration"},
    "Approver": {"Marketing", "Commercial", "CVM", "Campaign Operations", "Business Operations", "Legal & Regulatory"},
    "Data Analyst": {"Data & Analytics", "Finance"}, "Integration Admin": {"Technology & IT"},
    "Viewer": set(DEPARTMENTS) - {"Administration"},
}

DEPARTMENT_MODULES = {
    "Marketing": {"campaign-studio", "campaign-calendar", "scenario-studio", "customer-360", "audience-segments", "offer-management", "journey-orchestration", "workflow-automation", "campaign-execution", "nova-ai", "analytics-insights", "reports-exports", "business-rules", "approvals"},
    "Commercial": {"campaign-studio", "campaign-calendar", "customer-360", "scenario-studio", "audience-segments", "offer-management", "analytics-insights", "reports-exports", "business-rules", "approvals"},
    "CVM": {"campaign-studio", "scenario-studio", "customer-360", "audience-segments", "ai-segment-builder", "offer-management", "journey-orchestration", "workflow-automation", "campaign-execution", "nova-ai", "predictive-intelligence", "analytics-insights", "reports-exports", "business-rules", "approvals"},
    "Segments": {"customer-360", "audience-segments", "ai-segment-builder", "predictive-intelligence", "analytics-insights", "reports-exports"},
    "Customer Care": {"customer-360"},
    "Retail Sales": {"campaign-studio", "campaign-calendar", "customer-360", "scenario-studio", "offer-management", "analytics-insights", "reports-exports"},
    "Digital Services": {"campaign-studio", "campaign-calendar", "scenario-studio", "customer-360", "offer-management", "journey-orchestration", "workflow-automation", "campaign-execution", "business-rules", "analytics-insights", "reports-exports"},
    "Business Development": {"campaign-studio", "campaign-calendar", "customer-360", "scenario-studio", "offer-management", "analytics-insights", "reports-exports", "approvals"},
    "Business Operations": {"campaign-studio", "campaign-calendar", "scenario-studio", "audience-segments", "offer-management", "journey-orchestration", "workflow-automation", "campaign-execution", "business-rules", "approvals", "reports-exports"},
    "Product & Services": {"campaign-studio", "campaign-calendar", "scenario-studio", "customer-360", "audience-segments", "offer-management", "analytics-insights", "reports-exports"},
    "Operations": {"campaign-studio", "campaign-calendar", "scenario-studio", "audience-segments", "offer-management", "journey-orchestration", "workflow-automation", "campaign-execution", "business-rules", "approvals", "reports-exports"},
    "Carrier & International Wholesale": {"analytics-insights", "reports-exports"},
    "Campaign Operations": {"campaign-studio", "campaign-calendar", "scenario-studio", "audience-segments", "offer-management", "journey-orchestration", "workflow-automation", "campaign-execution", "business-rules", "approvals", "reports-exports"},
    "Data & Analytics": {"predictive-intelligence", "analytics-insights", "reports-exports", "ab-testing"},
    "Technology & IT": {"integrations", "channel-management", "settings", "audit-logs"},
    "Finance": {"analytics-insights", "reports-exports"},
    "People & Organization": set(),
    "Legal & Regulatory": {"approvals", "audit-logs", "business-rules", "reports-exports"},
    "Sales": {"campaign-studio", "campaign-calendar", "customer-360", "scenario-studio", "offer-management", "analytics-insights", "reports-exports"},
    "Customer Success": {"customer-360", "audience-segments", "analytics-insights", "reports-exports"},
    "Engineering": {"integrations", "channel-management", "settings", "audit-logs"},
    "Human Resources": set(),
}
_RATE_LIMITS: dict[str, list[float]] = {}
ROUTE_MODULES = (
    ("/dashboard", "dashboard"), ("/campaigns", "campaign-studio"), ("/scenarios", "scenario-studio"),
    ("/customers", "customer-360"), ("/segments", "audience-segments"), ("/offers", "offer-management"),
    ("/journeys", "journey-orchestration"), ("/business-rules", "business-rules"),
    ("/execution", "campaign-execution"), ("/approvals", "approvals"), ("/integrations", "integrations"),
    ("/ai", "nova-ai"), ("/intelligence", "analytics-insights"), ("/reports", "reports-exports"),
    ("/experiments", "ab-testing"),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _accounts() -> list[dict]:
    return [row for row in database.list_records("workspace_users") if row.get("account_type") == "user"]


def public_user(user: dict) -> dict:
    public = {key: value for key, value in user.items()
              if key not in {"password_hash", "avatar_data", "avatar_mime", "account_type", "tenant_id"}}
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                   if row.get("id") == user.get("tenant_id", "campaignnova-demo")), None)
    public["organization_name"] = user.get("organization_name") or (tenant or {}).get("name", "CampaignNova Demo Workspace")
    public["organization_slug"] = user.get("organization_slug") or (tenant or {}).get("slug", "campaignnova-demo")
    if user.get("avatar_data"):
        public["avatar_url"] = f"/api/auth/users/{user['id']}/avatar"
    return public


def valid_role_department(role: str, department: str) -> bool:
    return department in ROLE_DEPARTMENTS.get(role, set())


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}"


def _password_ok(password: str, saved: str) -> bool:
    try:
        algorithm, rounds, salt, expected = saved.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _rate_key(request: Request, purpose: str, email: str) -> str:
    address = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"{purpose}:{address}:{email.casefold()}".encode()).hexdigest()


def _rate_limit(key: str, limit: int, seconds: int) -> None:
    now = time.monotonic()
    recent = [stamp for stamp in _RATE_LIMITS.get(key, []) if now - stamp < seconds]
    if len(recent) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests. Wait a while and try again")
    recent.append(now)
    _RATE_LIMITS[key] = recent


def _validate_password(value: str) -> str:
    if len(value) < 12 or len(value) > 128:
        raise ValueError("Use a password between 12 and 128 characters")
    if not any(char.islower() for char in value) or not any(char.isupper() for char in value) or not any(char.isdigit() for char in value):
        raise ValueError("Include at least one uppercase letter, one lowercase letter, and one number")
    return value


def _validate_avatar(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    match = re.fullmatch(r"data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=]+)", value)
    if not match:
        raise ValueError("Profile photo must be a PNG, JPEG, or WebP image")
    try:
        content = base64.b64decode(match.group(2), validate=True)
    except ValueError:
        raise ValueError("Profile photo is not valid base64 image data") from None
    if len(content) > 15 * 1024 * 1024:
        raise ValueError("Profile photo must be 15 MB or smaller")
    mime = match.group(1)
    valid = ((mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
             or (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff"))
             or (mime == "image/webp" and content.startswith(b"RIFF") and content[8:12] == b"WEBP"))
    if not valid:
        raise ValueError("Image contents do not match the selected file type")
    return value


def _find_email(email: str) -> dict | None:
    normalized = email.strip().casefold()
    return next((row for row in _accounts() if row.get("email") == normalized), None)


def _save_user(user: dict) -> dict:
    database.save_record("workspace_users", user["id"], user)
    return user


def _new_session(response: Response, user: dict) -> None:
    token = secrets.token_urlsafe(40)
    expires_at = _now() + timedelta(hours=SESSION_HOURS)
    database.save_record("auth_sessions", _token_hash(token), {
        "id": _token_hash(token), "user_id": user["id"], "tenant_id": user.get("tenant_id", database.current_tenant()), "expires_at": expires_at.isoformat(),
        "created_at": _now().isoformat(),
    })
    secure = (os.getenv("CAMPAIGNNOVA_SECURE_COOKIES", "false").casefold() == "true"
              or os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production")
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_HOURS * 3600, httponly=True,
                        secure=secure, samesite="lax", path="/")


def _clear_session(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")


def _send_reset_email(recipient: str, reset_url: str) -> bool:
    host = os.getenv("SMTP_HOST")
    sender = os.getenv("SMTP_FROM_EMAIL")
    if not host or not sender:
        return False
    message = EmailMessage()
    message["Subject"] = "Reset your CampaignNova password"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(f"Use this one-time link to reset your password within 30 minutes:\n\n{reset_url}\n\nIf you did not request this, ignore this email.")
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as client:
        client.ehlo()
        if os.getenv("SMTP_STARTTLS", "true").casefold() == "true":
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        username = os.getenv("SMTP_USER")
        if username:
            client.login(username, os.getenv("SMTP_PASSWORD", ""))
        client.send_message(message)
    return True


def _request_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    token_digest = _token_hash(token)
    session = next((row for row in database.list_records("auth_sessions") if row.get("id") == token_digest), None)
    if not session or session.get("revoked") or _utc(session["expires_at"]) <= _now():
        raise HTTPException(status_code=401, detail="Your session has expired. Sign in again")
    if session.get("demo_guest"):
        return {
            "id": "campaignnova-demo-guest", "account_type": "demo_guest",
            "display_name": "CampaignNova Guest", "email": "guest@campaignnova.invalid",
            "tenant_id": session.get("tenant_id", "campaignnova-demo"),
            "organization_name": "CampaignNova Demo Workspace", "organization_slug": "campaignnova-demo",
            "department": "Data & Analytics", "role": "Viewer", "status": "Active",
            "must_change_password": False, "is_demo_guest": True,
        }
    user = next((row for row in _accounts() if row.get("id") == session.get("user_id")), None)
    if not user or user.get("status") != "Active":
        raise HTTPException(status_code=401, detail="This account is not active")
    return user


def require_user(request: Request) -> dict:
    user = _request_user(request)
    path = request.url.path.removeprefix("/api")
    department = user.get("department")
    role = user.get("role")
    method = request.method.upper()
    assistant_chat = path == "/ai/assist"
    if user.get("must_change_password") and path not in {"/auth/password", "/auth/me", "/auth/me/avatar", "/auth/logout"}:
        raise HTTPException(status_code=403, detail="Change your temporary password before accessing workspace data")
    origin = request.headers.get("origin")
    trusted_origins = {item.strip() for item in os.getenv(
        "CAMPAIGNNOVA_WEB_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")}
    if method not in {"GET", "HEAD", "OPTIONS"} and origin and origin not in trusted_origins:
        raise HTTPException(status_code=403, detail="Request origin is not allowed")
    if role not in ADMIN_ROLES:
        if path.startswith("/admin/") and department != "Technology & IT":
            raise HTTPException(status_code=403, detail="This area is restricted to administrators")
        if (path.startswith("/integrations") or path.startswith("/admin/settings")) and department != "Technology & IT":
            raise HTTPException(status_code=403, detail="This department does not have integration access")
        if role in READ_ONLY_ROLES and method not in {"GET", "HEAD", "OPTIONS"} and not assistant_chat:
            raise HTTPException(status_code=403, detail="Your assigned role has read-only access")
        if role == "Approver" and method not in {"GET", "HEAD", "OPTIONS"} and not assistant_chat and not re.fullmatch(r"/approvals/[^/]+/decision", path):
            raise HTTPException(status_code=403, detail="Approver accounts can only decide approval requests")
        module = next((key for prefix, key in ROUTE_MODULES if path == prefix or path.startswith(prefix + "/")), None)
        if module and module != "dashboard" and module not in DEPARTMENT_MODULES.get(department, set()) and not assistant_chat:
            raise HTTPException(status_code=403, detail=f"{department} department cannot access this workspace")
        if method == "PATCH" and re.fullmatch(r"/customers/[^/]+/consent", path) and role not in CONSENT_MANAGEMENT_ROLES:
            raise HTTPException(status_code=403, detail="Consent changes require a customer-value manager or administrator")
        module_match = re.match(r"^/modules/([^/]+)", path)
        if module_match:
            module_key = module_match.group(1)
            if module_key not in {"dashboard"} and module_key not in DEPARTMENT_MODULES.get(department, set()) and not assistant_chat:
                raise HTTPException(status_code=403, detail=f"{department} department cannot access this workspace")
        if path.startswith("/admin/settings") and role != "Integration Admin":
            raise HTTPException(status_code=403, detail="Workspace settings are restricted to administrators")
    return user


def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return user


def require_settings_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") not in ADMIN_ROLES and not (
        user.get("role") == "Integration Admin" and user.get("department") == "Technology & IT"
    ):
        raise HTTPException(status_code=403, detail="Workspace administrator access is required")
    return user


class Signup(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    password: str
    phone_country_code: str = "+92"
    phone_number: str = Field(min_length=7, max_length=18)
    department: str
    avatar_data: str | None = None
    bootstrap_token: str = ""

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid work email")
        return value

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _validate_password(value)

    @field_validator("phone_country_code")
    @classmethod
    def valid_phone_prefix(cls, value: str) -> str:
        value = value.strip()
        if not re.fullmatch(r"\+[1-9]\d{0,3}", value):
            raise ValueError("Choose a valid international country calling code")
        return value

    @field_validator("phone_number")
    @classmethod
    def valid_phone_number(cls, value: str) -> str:
        digits = re.sub(r"[\s()\-]", "", value)
        if not re.fullmatch(r"\d{7,15}", digits):
            raise ValueError("Enter a phone number using digits only")
        return digits

    @field_validator("department")
    @classmethod
    def valid_department(cls, value: str) -> str:
        if value not in DEPARTMENTS:
            raise ValueError("Choose a listed department")
        return value

    @field_validator("avatar_data")
    @classmethod
    def valid_avatar(cls, value: str | None) -> str | None:
        return _validate_avatar(value)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("company_name")
    @classmethod
    def clean_company_name(cls, value: str) -> str:
        return value.strip()


class Login(BaseModel):
    workspace_slug: str = Field(min_length=2, max_length=80)
    email: str
    password: str


class ForgotPassword(BaseModel):
    workspace_slug: str = Field(min_length=2, max_length=80)
    email: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().casefold()


class ResetPassword(BaseModel):
    workspace_slug: str = Field(min_length=2, max_length=80)
    token: str = Field(min_length=20, max_length=200)
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _validate_password(value)


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    phone_country_code: str = Field(pattern=r"^\+[1-9]\d{0,3}$")
    phone_number: str = Field(min_length=7, max_length=18)
    avatar_data: str | None = None

    @field_validator("avatar_data")
    @classmethod
    def valid_avatar(cls, value: str | None) -> str | None:
        return _validate_avatar(value)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return _validate_password(value)


@router.get("/setup-status")
def setup_status():
    return {"setup_required": False, "departments": list(DEPARTMENTS),
            "roles": list(ROLES), "organization": "CampaignNova",
            "bootstrap_token_required": os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production"}


@router.post("/signup", status_code=201)
def signup(payload: Signup, response: Response):
    slug = re.sub(r"[^a-z0-9]+", "-", payload.company_name.casefold()).strip("-")[:70].strip("-")
    if len(slug) < 2:
        raise HTTPException(status_code=422, detail="Enter a company name that can identify its workspace")
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                   if row.get("slug") == slug), None)
    if slug == "campaignnova-demo":
        raise HTTPException(status_code=409, detail="This workspace code is reserved")
    if tenant is None:
        tenant = {"id": slug, "slug": slug, "name": payload.company_name, "created_at": _now().isoformat(), "tenant_id": "__global__"}
        database.save_record("workspace_tenants", slug, tenant)
    database.set_tenant(tenant["id"])
    if _find_email(payload.email):
        raise HTTPException(status_code=409, detail="An account already uses this email")
    first_account = len(_accounts()) == 0
    if first_account and os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production":
        bootstrap = os.getenv("CAMPAIGNNOVA_BOOTSTRAP_TOKEN", "")
        if not bootstrap or not hmac.compare_digest(payload.bootstrap_token, bootstrap):
            raise HTTPException(status_code=403, detail="Initial account setup requires the configured administrator bootstrap token")
    now = _now().isoformat()
    user = {
        "id": f"usr-{uuid4().hex[:12]}", "account_type": "user", "display_name": payload.display_name,
        "tenant_id": tenant["id"], "organization_name": tenant["name"], "organization_slug": tenant["slug"],
        "email": payload.email, "phone_country_code": payload.phone_country_code,
        "phone_number": payload.phone_number, "department": "Administration" if first_account else payload.department,
        "role": "Super Admin" if first_account else "Viewer",
        "status": "Active" if first_account else "Pending Approval", "must_change_password": False,
        "avatar_data": payload.avatar_data, "avatar_mime": payload.avatar_data.split(";", 1)[0][5:] if payload.avatar_data else None,
        "password_hash": _password_hash(payload.password), "created_at": now, "updated_at": now,
    }
    _save_user(user)
    record_audit_event(user["email"], "account_created", "user", user["id"],
                       {"department": user["department"], "role": user["role"], "status": user["status"]})
    if first_account:
        _new_session(response, user)
    return {"user": public_user(user), "first_account": first_account, "workspace_slug": tenant["slug"],
            "message": "Initial administrator account created." if first_account else "Signup received. An administrator must approve the account before sign-in."}


@router.post("/login")
def login(payload: Login, request: Request, response: Response):
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                   if row.get("slug") == payload.workspace_slug.strip().casefold()), None)
    if not tenant:
        raise HTTPException(status_code=401, detail="Workspace, email, or password is incorrect")
    database.set_tenant(tenant["id"])
    limit_key = _rate_key(request, "login", payload.workspace_slug + ":" + payload.email)
    _rate_limit(limit_key, 6, 900)
    user = _find_email(payload.email)
    # A fixed-cost verification on unknown addresses reduces response-time enumeration.
    if user is None:
        _password_hash("InvalidPassword123", bytes.fromhex("00112233445566778899aabbccddeeff"))
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if not _password_ok(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    if user.get("status") != "Active":
        raise HTTPException(status_code=403, detail="Your account is awaiting administrator approval or is disabled")
    user["last_login_at"] = _now().isoformat()
    _save_user(user)
    _RATE_LIMITS.pop(limit_key, None)
    _new_session(response, user)
    record_audit_event(user["email"], "signed_in", "user", user["id"])
    return {"user": public_user(user)}


@router.post("/demo-login")
def demo_login(request: Request, response: Response):
    """Create a read-only session scoped to the seeded CampaignNova demo tenant."""
    if os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production" and os.getenv(
        "CAMPAIGNNOVA_DEMO_MODE", "false"
    ).casefold() != "true":
        raise HTTPException(status_code=404, detail="Demo access is not enabled")
    _rate_limit(_rate_key(request, "demo-login", "guest"), 10, 900)
    tenant_id = "campaignnova-demo"
    database.set_tenant(tenant_id)
    token = secrets.token_urlsafe(40)
    expires_at = _now() + timedelta(hours=SESSION_HOURS)
    database.save_record("auth_sessions", _token_hash(token), {
        "id": _token_hash(token), "user_id": "campaignnova-demo-guest", "tenant_id": tenant_id,
        "demo_guest": True, "expires_at": expires_at.isoformat(), "created_at": _now().isoformat(),
    })
    secure = (os.getenv("CAMPAIGNNOVA_SECURE_COOKIES", "false").casefold() == "true"
              or os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production")
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_HOURS * 3600, httponly=True,
                        secure=secure, samesite="lax", path="/")
    guest = _request_user_from_demo(tenant_id)
    return {"user": public_user(guest), "access": "read-only", "modules": ["dashboard", "analytics-insights", "reports-exports", "predictive-intelligence", "ab-testing"]}


def _request_user_from_demo(tenant_id: str) -> dict:
    return {
        "id": "campaignnova-demo-guest", "account_type": "demo_guest",
        "display_name": "CampaignNova Guest", "email": "guest@campaignnova.invalid",
        "tenant_id": tenant_id, "organization_name": "CampaignNova Demo Workspace",
        "organization_slug": tenant_id, "department": "Data & Analytics", "role": "Viewer",
        "status": "Active", "must_change_password": False, "is_demo_guest": True,
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        database.save_record("auth_sessions", _token_hash(token), {
            "id": _token_hash(token), "revoked": True, "revoked_at": _now().isoformat(),
        })
    _clear_session(response)
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(_request_user)):
    return public_user(user)


@router.patch("/me")
def update_profile(payload: ProfileUpdate, user: dict = Depends(_request_user)):
    phone = re.sub(r"[\s()\-]", "", payload.phone_number)
    if not re.fullmatch(r"\d{7,15}", phone):
        raise HTTPException(status_code=422, detail="Enter a phone number using 7–15 digits")
    user.update({"display_name": payload.display_name.strip(), "phone_country_code": payload.phone_country_code,
                 "phone_number": phone, "updated_at": _now().isoformat()})
    if "avatar_data" in payload.model_fields_set:
        user["avatar_data"] = payload.avatar_data
        user["avatar_mime"] = payload.avatar_data.split(";", 1)[0][5:] if payload.avatar_data else None
    _save_user(user)
    record_audit_event(user["email"], "profile_updated", "user", user["id"])
    return public_user(user)


@router.get("/me/avatar")
def get_avatar(user: dict = Depends(_request_user)):
    if not user.get("avatar_data"):
        raise HTTPException(status_code=404, detail="No profile image has been uploaded")
    content = base64.b64decode(user["avatar_data"].split(",", 1)[1])
    return RawResponse(content, media_type=user.get("avatar_mime") or "image/png",
                       headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/users/{user_id}/avatar")
def get_user_avatar(user_id: str, user: dict = Depends(_request_user)):
    target = next((row for row in _accounts() if row.get("id") == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Account not found")
    if target["id"] != user["id"] and user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="You can only view your own profile image")
    if not target.get("avatar_data"):
        raise HTTPException(status_code=404, detail="No profile image has been uploaded")
    content = base64.b64decode(target["avatar_data"].split(",", 1)[1])
    return RawResponse(content, media_type=target.get("avatar_mime") or "image/png",
                       headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.post("/password")
def change_password(payload: PasswordChange, response: Response, user: dict = Depends(_request_user)):
    if not _password_ok(payload.current_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user["password_hash"] = _password_hash(payload.new_password)
    user["must_change_password"] = False
    user["updated_at"] = _now().isoformat()
    _save_user(user)
    for session in database.list_records("auth_sessions"):
        if session.get("user_id") == user["id"]:
            database.save_record("auth_sessions", session["id"], {**session, "revoked": True})
    _new_session(response, user)
    record_audit_event(user["email"], "password_changed", "user", user["id"])
    return {"ok": True, "user": public_user(user)}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPassword, request: Request):
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                   if row.get("slug") == payload.workspace_slug.strip().casefold()), None)
    if not tenant:
        return {"message": "If an active account matches that email and workspace, password reset instructions are ready."}
    database.set_tenant(tenant["id"])
    _rate_limit(_rate_key(request, "password-reset", payload.email), 5, 3600)
    user = _find_email(payload.email)
    response_body: dict = {"message": "If an active account matches that email, password reset instructions are ready."}
    if user and user.get("status") == "Active":
        token = secrets.token_urlsafe(36)
        digest = _token_hash(token)
        expires = _now() + timedelta(minutes=RESET_MINUTES)
        database.save_record("password_resets", digest, {"id": digest, "user_id": user["id"],
                               "expires_at": expires.isoformat(), "created_at": _now().isoformat()})
        record_audit_event(user["email"], "password_reset_requested", "user", user["id"])
        public_web = os.getenv("CAMPAIGNNOVA_PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")
        reset_url = f"{public_web}/reset-password?workspace={tenant['slug']}&token={token}"
        try:
            delivered = _send_reset_email(user["email"], reset_url)
        except (OSError, smtplib.SMTPException):
            delivered = False
        if os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "development" and not delivered:
            response_body["development_reset_url"] = reset_url
            response_body["development_only"] = True
    return response_body


@router.post("/reset-password")
def reset_password(payload: ResetPassword):
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                   if row.get("slug") == payload.workspace_slug.strip().casefold()), None)
    if not tenant:
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")
    database.set_tenant(tenant["id"])
    digest = _token_hash(payload.token)
    reset = next((row for row in database.list_records("password_resets") if row.get("id") == digest), None)
    if not reset or reset.get("used_at") or _utc(reset["expires_at"]) <= _now():
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")
    user = next((row for row in _accounts() if row.get("id") == reset["user_id"]), None)
    if not user or user.get("status") != "Active":
        raise HTTPException(status_code=400, detail="This password reset link is invalid or expired")
    user["password_hash"] = _password_hash(payload.new_password)
    user["must_change_password"] = False
    user["updated_at"] = _now().isoformat()
    _save_user(user)
    database.save_record("password_resets", digest, {**reset, "used_at": _now().isoformat()})
    for session in database.list_records("auth_sessions"):
        if session.get("user_id") == user["id"]:
            database.save_record("auth_sessions", session["id"], {**session, "revoked": True})
    record_audit_event(user["email"], "password_reset_completed", "user", user["id"])
    return {"ok": True, "message": "Password updated. Sign in with your new password."}
