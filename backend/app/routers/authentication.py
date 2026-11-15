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
from urllib.parse import parse_qsl, urlsplit
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import Response as RawResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, ValidationInfo, field_validator

from .. import database
from ..services.audit import record_audit_event

router = APIRouter(prefix="/auth", tags=["authentication"])
SESSION_COOKIE = "campaignnova_session"
SESSION_HOURS = 12
REMEMBER_DAYS = 30
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
MODULE_TITLES = {
    "dashboard": "Executive Dashboard",
    "scenario-studio": "Scenario Studio", "campaign-studio": "Campaign Studio",
    "campaign-calendar": "Campaign Calendar", "customer-360": "Customer 360",
    "audience-segments": "Audience & Segments", "ai-segment-builder": "AI Segment Builder",
    "offer-management": "Offer Management", "journey-orchestration": "Journey Orchestration",
    "workflow-automation": "Workflow Automation", "campaign-execution": "Campaign Execution",
    "channel-management": "Channel Management", "nova-ai": "Nova AI Assistant",
    "predictive-intelligence": "Predictive Intelligence", "ab-testing": "A/B Testing",
    "analytics-insights": "Analytics & Insights", "reports-exports": "Reports & Exports",
    "integrations": "Data Integration Hub", "business-rules": "Business Rules Engine",
    "approvals": "Approvals & Governance", "user-roles": "User & Role Management",
    "audit-logs": "Audit Logs", "settings": "System Configuration", "feature-access": "Feature Access",
}
MODULE_KEYS = tuple(MODULE_TITLES)
DEFAULT_ENABLED_MODULES = ["dashboard", "campaign-studio", "campaign-calendar", "customer-360", "audience-segments", "offer-management", "campaign-execution", "analytics-insights", "reports-exports", "approvals", "user-roles", "settings", "feature-access"]
COMPANY_LOGOS = {
    "ptcl": "/company-logos/ptcl.svg", "jazz": "/company-logos/jazz.png",
    "zong": "/company-logos/zong.svg", "ufone": "/company-logos/ufone.png",
    "telenor": "/company-logos/telenor.png", "nayatel": "/company-logos/nayatel.jpg",
    "stormfiber": "/company-logos/stormfiber.svg", "transworld": "/company-logos/transworld.svg",
    "wateen": "/company-logos/wateen.png", "cybernet": "/company-logos/cybernet.svg",
    "fiberlink": "/company-logos/fiberlink.jpg",
}
PHONE_LENGTHS = {
    "+1": (10, 10), "+44": (10, 10), "+971": (9, 9), "+91": (10, 10),
    "+966": (9, 9), "+974": (8, 8), "+86": (11, 11), "+90": (10, 10),
    "+61": (9, 9), "+49": (7, 11), "+33": (9, 9), "+880": (10, 10),
    "+93": (9, 9), "+92": (10, 10),
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
API_MODULE_ALIASES = {
    "campaign-studio": {"campaign-studio", "campaign-calendar"},
    "audience-segments": {"audience-segments", "ai-segment-builder"},
    "integrations": {"integrations", "channel-management"},
}
OAUTH_PROVIDER_INFO = {
    "google": {"name": "Google", "discovery": "https://accounts.google.com/.well-known/openid-configuration", "prefix": "GOOGLE"},
    "microsoft": {"name": "Microsoft", "discovery": "https://login.microsoftonline.com/common/v2.0/.well-known/openid-configuration", "prefix": "MICROSOFT"},
    "yahoo": {"name": "Yahoo", "discovery": "https://api.login.yahoo.com/.well-known/openid-configuration", "prefix": "YAHOO"},
    "apple": {"name": "Apple", "discovery": "https://appleid.apple.com/.well-known/openid-configuration", "prefix": "APPLE"},
}
OAUTH_CLIENTS = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _workspace_settings(tenant_id: str | None = None) -> dict:
    settings = database.list_records("workspace_settings", tenant_id=tenant_id or database.current_tenant())
    return next((row for row in settings if row.get("id") == "workspace-defaults"), {})


def _enabled_modules(tenant_id: str | None = None) -> list[str]:
    configured = _workspace_settings(tenant_id).get("enabled_modules")
    if isinstance(configured, list):
        return [key for key in MODULE_KEYS if key == "dashboard" or key in configured]
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*") if row.get("id") == (tenant_id or database.current_tenant())), None)
    return list(MODULE_KEYS) if not tenant or tenant.get("slug") == "campaignnova-demo" else list(DEFAULT_ENABLED_MODULES)


def _department_enabled_modules(department: str, tenant_id: str | None = None) -> set[str]:
    settings = _workspace_settings(tenant_id)
    custom = settings.get("department_module_access", {}).get(department)
    return set(custom) if isinstance(custom, list) else set(DEPARTMENT_MODULES.get(department, set()))


def _validate_phone_number(value: str, country_code: str) -> str:
    if not re.fullmatch(r"[0-9]{7,15}", value):
        raise ValueError("Enter a phone number using digits only")
    length_range = PHONE_LENGTHS.get(country_code)
    if length_range and not length_range[0] <= len(value) <= length_range[1]:
        low, high = length_range
        expected = f"{low}" if low == high else f"{low}–{high}"
        raise ValueError(f"Enter a {expected}-digit national phone number for this country")
    return value


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _accounts() -> list[dict]:
    return [row for row in database.list_records("workspace_users") if row.get("account_type") == "user"]


def public_user(user: dict) -> dict:
    public = {key: value for key, value in user.items()
              if key not in {"password_hash", "avatar_data", "avatar_mime", "account_type", "tenant_id"}}
    tenant_id = user.get("tenant_id", "campaignnova-demo")
    tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                   if row.get("id") == tenant_id), None)
    tenant_settings = _workspace_settings(tenant_id)
    public["organization_name"] = (tenant or {}).get("name") or user.get("organization_name", "CampaignNova Demo Workspace")
    public["organization_slug"] = user.get("organization_slug") or (tenant or {}).get("slug", "campaignnova-demo")
    public["enabled_modules"] = _enabled_modules(tenant_id)
    public["department_modules"] = sorted(_department_enabled_modules(user.get("department", ""), tenant_id))
    if tenant_settings.get("logo_data"):
        public["organization_logo_url"] = f"/api/auth/workspaces/{public['organization_slug']}/logo"
    elif tenant:
        public["organization_logo_url"] = tenant.get("logo_url") or COMPANY_LOGOS.get(tenant.get("slug", ""))
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


def _new_session(response: Response, user: dict, remember_me: bool = False) -> None:
    token = secrets.token_urlsafe(40)
    max_age = REMEMBER_DAYS * 24 * 60 * 60 if remember_me else SESSION_HOURS * 3600
    expires_at = _now() + timedelta(seconds=max_age)
    database.save_record("auth_sessions", _token_hash(token), {
        "id": _token_hash(token), "user_id": user["id"], "tenant_id": user.get("tenant_id", database.current_tenant()), "expires_at": expires_at.isoformat(),
        "created_at": _now().isoformat(),
    })
    secure = (os.getenv("CAMPAIGNNOVA_SECURE_COOKIES", "false").casefold() == "true"
              or os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production")
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True,
                        secure=secure, samesite="none" if secure else "lax", path="/")


def _clear_session(response: Response) -> None:
    secure = (os.getenv("CAMPAIGNNOVA_SECURE_COOKIES", "false").casefold() == "true"
              or os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production")
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True,
                           secure=secure, samesite="none" if secure else "lax")


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
    now = _now()
    last_seen = session.get("last_seen_at")
    if not last_seen or (now - _utc(last_seen)).total_seconds() >= 60:
        database.save_record("auth_sessions", session["id"], {**session, "last_seen_at": now.isoformat()})
    return user


def _user_can_access_module(user: dict, module: str) -> bool:
    if module not in MODULE_TITLES:
        return False
    enabled = _enabled_modules(user.get("tenant_id"))
    if module not in enabled:
        return False
    assigned_modules = user.get("module_access")
    # An explicit account policy can narrow even an administrator's workspace
    # modules. `None` keeps the normal role defaults.
    if user.get("role") in ADMIN_ROLES:
        return not isinstance(assigned_modules, list) or module in assigned_modules
    if isinstance(assigned_modules, list):
        return module in assigned_modules
    if module == "dashboard":
        return True
    if module == "feature-access":
        return True
    department_modules = _department_enabled_modules(user.get("department", ""), user.get("tenant_id"))
    return module in department_modules


def _user_can_access_api_module(user: dict, module: str, path: str, method: str) -> bool:
    aliases = API_MODULE_ALIASES.get(module, {module})
    if module == "campaign-studio" and method not in {"GET", "HEAD", "OPTIONS"}:
        aliases = {"campaign-studio"}
    if method in {"GET", "HEAD", "OPTIONS"} and path.startswith(
        ("/journeys", "/business-rules", "/execution")
    ):
        aliases = aliases | {"workflow-automation"}
    return any(_user_can_access_module(user, alias) for alias in aliases)


def require_user(request: Request) -> dict:
    user = _request_user(request)
    path = request.url.path.removeprefix("/api")
    department = user.get("department")
    role = user.get("role")
    method = request.method.upper()
    assistant_chat = path == "/ai/assist"
    feature_request_submission = method == "POST" and path == "/feature-access/requests"
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
        if role in READ_ONLY_ROLES and method not in {"GET", "HEAD", "OPTIONS"} and not assistant_chat and not feature_request_submission:
            raise HTTPException(status_code=403, detail="Your assigned role has read-only access")
        if role == "Approver" and method not in {"GET", "HEAD", "OPTIONS"} and not assistant_chat and not re.fullmatch(r"/approvals/[^/]+/decision", path):
            raise HTTPException(status_code=403, detail="Approver accounts can only decide approval requests")
        if method == "PATCH" and re.fullmatch(r"/customers/[^/]+/consent", path) and role not in CONSENT_MANAGEMENT_ROLES:
            raise HTTPException(status_code=403, detail="Consent changes require a customer-value manager or administrator")
        if path.startswith("/admin/settings") and role != "Integration Admin":
            raise HTTPException(status_code=403, detail="Workspace settings are restricted to administrators")
    module = next((key for prefix, key in ROUTE_MODULES if path == prefix or path.startswith(prefix + "/")), None)
    if path.startswith("/admin/settings"):
        module = "settings"
    elif path.startswith(("/admin/users", "/admin/roles", "/admin/overview", "/admin/companies")):
        module = "user-roles"
    module_match = re.match(r"^/modules/([^/]+)", path)
    if module_match:
        module = module_match.group(1)
    if path.startswith("/feature-access"):
        module = "feature-access"
    if module and not _user_can_access_api_module(user, module, path, method):
        raise HTTPException(status_code=403, detail="This module is not enabled for your account")
    return user


def require_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Administrator access is required")
    return user


def require_super_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") != "Super Admin":
        raise HTTPException(status_code=403, detail="Super Admin access is required")
    return user


def require_settings_admin(user: dict = Depends(require_user)) -> dict:
    if user.get("role") not in ADMIN_ROLES and not (
        user.get("role") == "Integration Admin" and user.get("department") == "Technology & IT"
    ):
        raise HTTPException(status_code=403, detail="Workspace administrator access is required")
    return user


class Signup(BaseModel):
    workspace_slug: str | None = Field(default=None, min_length=2, max_length=80)
    signup_type: Literal["user", "super_admin", "company"] = "user"
    company_name: str | None = Field(default=None, min_length=2, max_length=120)
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
    def valid_phone_number(cls, value: str, info: ValidationInfo) -> str:
        return _validate_phone_number(value, info.data.get("phone_country_code", "+92"))

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
    def clean_company_name(cls, value: str | None) -> str | None:
        return value.strip() if value else value


class Login(BaseModel):
    workspace_slug: str = Field(min_length=2, max_length=80)
    email: str
    password: str
    remember_me: bool = False


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

    @field_validator("phone_number")
    @classmethod
    def valid_phone_number(cls, value: str, info: ValidationInfo) -> str:
        return _validate_phone_number(value, info.data.get("phone_country_code", "+92"))


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


@router.get("/workspaces/{workspace_slug}")
def workspace_brand(workspace_slug: str):
    tenant = database.global_record("workspace_tenants", workspace_slug.strip().casefold())
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    settings = _workspace_settings(tenant["id"])
    logo_url = (f"/api/auth/workspaces/{tenant['slug']}/logo" if settings.get("logo_data")
                else tenant.get("logo_url") or COMPANY_LOGOS.get(tenant.get("slug", "")))
    return {"name": tenant["name"], "slug": tenant["slug"], "logo_url": logo_url}


@router.get("/workspaces")
def list_workspaces():
    rows = [row for row in database.list_records("workspace_tenants", tenant_id="*")
            if row.get("slug") != "campaignnova-demo"]
    workspaces = []
    for tenant in rows:
        settings = _workspace_settings(tenant["id"])
        logo_url = (f"/api/auth/workspaces/{tenant['slug']}/logo" if settings.get("logo_data")
                    else tenant.get("logo_url") or COMPANY_LOGOS.get(tenant.get("slug", "")))
        accounts = [row for row in database.list_records("workspace_users", tenant_id=tenant["id"])
                    if row.get("account_type") == "user"]
        has_active_admin = any(row.get("status") == "Active" and row.get("role") in ADMIN_ROLES for row in accounts)
        workspaces.append({"name": tenant["name"], "slug": tenant["slug"], "logo_url": logo_url,
                           "user_signup_available": has_active_admin,
                           "super_admin_setup_available": not accounts})
    return sorted(workspaces, key=lambda row: row["name"].casefold())


@router.get("/workspaces/{workspace_slug}/logo")
def workspace_logo(workspace_slug: str):
    tenant = database.global_record("workspace_tenants", workspace_slug.strip().casefold())
    if not tenant:
        raise HTTPException(status_code=404, detail="Workspace not found")
    logo_data = _workspace_settings(tenant["id"]).get("logo_data")
    if not logo_data:
        raise HTTPException(status_code=404, detail="No company logo has been uploaded")
    content = base64.b64decode(logo_data.split(",", 1)[1])
    mime = logo_data[5:].split(";", 1)[0]
    return RawResponse(content, media_type=mime,
                       headers={"Cache-Control": "public, max-age=300", "X-Content-Type-Options": "nosniff"})


@router.post("/signup", status_code=201)
def signup(payload: Signup, response: Response):
    if payload.signup_type == "company":
        raise HTTPException(status_code=403, detail="Only a signed-in Super Admin can create a company workspace")
    slug = (payload.workspace_slug or "").strip().casefold()
    tenant = database.global_record("workspace_tenants", slug)
    if not tenant or tenant.get("slug") == "campaignnova-demo":
        raise HTTPException(status_code=404, detail="Choose a company workspace from the list")
    database.set_tenant(tenant["id"])
    if _find_email(payload.email):
        raise HTTPException(status_code=409, detail="An account already uses this email")
    first_account = len(_accounts()) == 0
    if payload.signup_type == "user" and first_account:
        raise HTTPException(status_code=409, detail="This company needs its initial Super Admin setup before users can join")
    if payload.signup_type == "super_admin" and not first_account:
        raise HTTPException(status_code=409, detail="This company already has an administrator. Request a user account instead.")
    if payload.signup_type == "super_admin" and os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production":
        bootstrap = os.getenv("CAMPAIGNNOVA_BOOTSTRAP_TOKEN", "")
        if not bootstrap or not hmac.compare_digest(payload.bootstrap_token, bootstrap):
            raise HTTPException(status_code=403, detail="Initial account setup requires the configured administrator bootstrap token")
    is_super_admin = payload.signup_type == "super_admin"
    now = _now().isoformat()
    user = {
        "id": f"usr-{uuid4().hex[:12]}", "account_type": "user", "display_name": payload.display_name,
        "tenant_id": tenant["id"], "organization_name": tenant["name"], "organization_slug": tenant["slug"],
        "email": payload.email, "phone_country_code": payload.phone_country_code,
        "phone_number": payload.phone_number, "department": "Administration" if is_super_admin else payload.department,
        "role": "Super Admin" if is_super_admin else "Viewer",
        "status": "Active" if is_super_admin else "Pending Approval", "must_change_password": False,
        "avatar_data": payload.avatar_data, "avatar_mime": payload.avatar_data.split(";", 1)[0][5:] if payload.avatar_data else None,
        "password_hash": _password_hash(payload.password), "created_at": now, "updated_at": now,
    }
    _save_user(user)
    if is_super_admin and first_account:
        database.save_record("workspace_settings", "workspace-defaults", {
            "id": "workspace-defaults", "workspace_name": tenant["name"], "enabled_modules": list(DEFAULT_ENABLED_MODULES),
            "department_module_access": {}, "logo_data": None, "timezone": "UTC", "currency": "USD",
            "date_format": "YYYY-MM-DD", "default_channel": "SMS", "tenant_id": tenant["id"],
        })
    record_audit_event(user["email"], "account_created", "user", user["id"],
                       {"department": user["department"], "role": user["role"], "status": user["status"]})
    if is_super_admin:
        _new_session(response, user)
    return {"user": public_user(user), "first_account": first_account, "super_admin_created": is_super_admin,
            "workspace_slug": tenant["slug"],
            "message": "Super Admin account created." if is_super_admin else "Signup received. A company Super Admin must approve the account before sign-in."}


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
    _new_session(response, user, payload.remember_me)
    record_audit_event(user["email"], "signed_in", "user", user["id"])
    return {"user": public_user(user)}


def _oauth_is_configured(provider: str) -> bool:
    info = OAUTH_PROVIDER_INFO.get(provider)
    if not info or not os.getenv("CAMPAIGNNOVA_OAUTH_SESSION_SECRET"):
        return False
    prefix = info["prefix"]
    configured = bool(os.getenv(f"CAMPAIGNNOVA_OAUTH_{prefix}_CLIENT_ID")
                      and os.getenv(f"CAMPAIGNNOVA_OAUTH_{prefix}_CLIENT_SECRET"))
    if provider == "apple":
        api_url = os.getenv("CAMPAIGNNOVA_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
        secure = (os.getenv("CAMPAIGNNOVA_SECURE_COOKIES", "false").casefold() == "true"
                  or os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production")
        configured = configured and secure and api_url.startswith("https://")
    return configured


def _oauth_clients():
    global OAUTH_CLIENTS
    if OAUTH_CLIENTS is not None:
        return OAUTH_CLIENTS
    try:
        from authlib.integrations.starlette_client import OAuth
    except ImportError:
        return None
    registry = OAuth()
    for provider, info in OAUTH_PROVIDER_INFO.items():
        if not _oauth_is_configured(provider):
            continue
        prefix = info["prefix"]
        registry.register(
            name=provider,
            client_id=os.getenv(f"CAMPAIGNNOVA_OAUTH_{prefix}_CLIENT_ID"),
            client_secret=os.getenv(f"CAMPAIGNNOVA_OAUTH_{prefix}_CLIENT_SECRET"),
            server_metadata_url=info["discovery"],
            client_kwargs={"scope": "openid email" if provider == "apple" else "openid email profile"},
        )
    OAUTH_CLIENTS = registry
    return registry


def _oauth_callback_uri(provider: str) -> str:
    api_url = os.getenv("CAMPAIGNNOVA_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    return f"{api_url}/api/auth/oauth/{provider}/callback"


def _oauth_user_binding(user: dict) -> str:
    secret = os.getenv("CAMPAIGNNOVA_OAUTH_SESSION_SECRET", "")
    subject = f"{user.get('tenant_id', '')}:{user.get('id', '')}".encode()
    return hmac.new(secret.encode(), subject, hashlib.sha256).hexdigest()


def _oauth_redirect_url(error: str | None = None) -> str:
    base = os.getenv("CAMPAIGNNOVA_PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")
    return f"{base}/login" + (f"?error={error}" if error else "")


def _oauth_completion_url(context: dict, error: str | None = None) -> str:
    base = os.getenv("CAMPAIGNNOVA_PUBLIC_WEB_URL", "http://localhost:3000").rstrip("/")
    if context.get("popup"):
        return f"{base}/oauth-popup?" + (f"error={error}" if error else "result=success")
    return _oauth_redirect_url(error) if error else f"{base}/"


@router.get("/oauth/providers")
def oauth_providers(workspace_slug: str | None = None):
    if workspace_slug:
        tenant = database.global_record("workspace_tenants", workspace_slug.strip().casefold())
        if not tenant or tenant.get("slug") == "campaignnova-demo":
            raise HTTPException(status_code=404, detail="Choose a registered company workspace")
    return [{"id": provider, "name": info["name"], "configured": _oauth_is_configured(provider)}
            for provider, info in OAUTH_PROVIDER_INFO.items()]


@router.get("/oauth/identities")
def oauth_identities(current: dict = Depends(require_user)):
    linked = {row.get("provider") for row in database.list_records("oauth_identities")
              if row.get("user_id") == current["id"]}
    return [{"id": provider, "name": info["name"], "configured": _oauth_is_configured(provider),
             "linked": provider in linked} for provider, info in OAUTH_PROVIDER_INFO.items()]


@router.get("/oauth/{provider}/start")
async def oauth_start(provider: str, request: Request, workspace_slug: str | None = None,
                      intent: Literal["login", "link"] = "login", popup: bool = False):
    provider = provider.casefold()
    _rate_limit(_rate_key(request, f"oauth-{provider}", intent), 6, 900)
    if provider not in OAUTH_PROVIDER_INFO or not _oauth_is_configured(provider):
        raise HTTPException(status_code=503, detail="This sign-in provider has not been configured")
    registry = _oauth_clients()
    if registry is None:
        raise HTTPException(status_code=503, detail="OAuth support is not installed; install backend requirements")
    if intent == "link":
        current = _request_user(request)
        if current.get("account_type") != "user" or current.get("must_change_password"):
            raise HTTPException(status_code=403, detail="Sign in to a regular account and change any temporary password before linking providers")
        tenant = next((row for row in database.list_records("workspace_tenants", tenant_id="*")
                       if row.get("id") == current.get("tenant_id")), None)
        if not tenant:
            raise HTTPException(status_code=404, detail="Your company workspace was not found")
        workspace_slug = tenant["slug"]
        link_user_binding = _oauth_user_binding(current)
    else:
        tenant = database.global_record("workspace_tenants", (workspace_slug or "").strip().casefold())
        if not tenant or tenant.get("slug") == "campaignnova-demo":
            raise HTTPException(status_code=400, detail="Choose a company workspace before using social sign-in")
        link_user_binding = None
    client = registry.create_client(provider)
    response_mode = "form_post" if provider == "apple" else None
    kwargs = {"response_mode": response_mode, "nonce": secrets.token_urlsafe(24)} if response_mode else {}
    if provider in {"google", "microsoft"}:
        # Send the user to the provider's account chooser/login screen instead
        # of silently reusing a previously authenticated provider session.
        kwargs["prompt"] = "select_account"
    response = await client.authorize_redirect(request, _oauth_callback_uri(provider), **kwargs)
    location = response.headers.get("location", "")
    state = next((value for key, value in parse_qsl(urlsplit(location).query) if key == "state"), None)
    if not state:
        raise HTTPException(status_code=502, detail="The identity provider could not start sign-in")
    contexts = request.session.get("campaignnova_oauth_contexts", {})
    contexts[state] = {"provider": provider, "workspace_slug": tenant["slug"],
                       "intent": intent, "link_user_binding": link_user_binding,
                       "popup": popup and intent == "login",
                       "created_at": int(time.time())}
    request.session["campaignnova_oauth_contexts"] = dict(list(contexts.items())[-4:])
    return response


@router.get("/oauth/{provider}/callback")
@router.post("/oauth/{provider}/callback")
async def oauth_callback(provider: str, request: Request):
    provider = provider.casefold()
    registry = _oauth_clients()
    if provider not in OAUTH_PROVIDER_INFO or not _oauth_is_configured(provider) or registry is None:
        return RedirectResponse(_oauth_redirect_url("provider_unavailable"), status_code=303)
    if request.method == "GET":
        state = request.query_params.get("state", "")
    else:
        form_data = await request.form()
        state = str(form_data.get("state", ""))
    contexts = request.session.get("campaignnova_oauth_contexts", {})
    context = contexts.pop(state, None) if state else None
    request.session["campaignnova_oauth_contexts"] = contexts
    if not context or context.get("provider") != provider or int(time.time()) - context.get("created_at", 0) > 600:
        return RedirectResponse(_oauth_redirect_url("state_invalid"), status_code=303)
    try:
        client = registry.create_client(provider)
        token = await client.authorize_access_token(
            request, claims_options={"iss": {"essential": True}} if provider == "microsoft" else None
        )
        identity = token.get("userinfo") or {}
        subject = str(identity.get("sub") or "").strip()
        email = str(identity.get("email") or "").strip().casefold()
        if not subject:
            raise ValueError("Identity provider did not return a subject identifier")
        if provider == "microsoft":
            tenant_claim = str(identity.get("tid") or "")
            expected_issuer = f"https://login.microsoftonline.com/{tenant_claim}/v2.0"
            if not re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", tenant_claim) or identity.get("iss") != expected_issuer:
                raise ValueError("Microsoft token issuer and tenant claims do not match")
        tenant = database.global_record("workspace_tenants", context["workspace_slug"])
        if not tenant or tenant.get("slug") == "campaignnova-demo":
            return RedirectResponse(_oauth_completion_url(context, "workspace_unavailable"), status_code=303)
        database.set_tenant(tenant["id"])
        identity_key = f"{provider}-{hashlib.sha256(subject.encode()).hexdigest()}"
        existing_identity = next((row for row in database.list_records("oauth_identities")
                                  if row.get("id") == identity_key), None)
        if context["intent"] == "link":
            current = _request_user(request)
            if (not hmac.compare_digest(_oauth_user_binding(current), str(context.get("link_user_binding", "")))
                    or current.get("tenant_id") != tenant["id"]
                    or current.get("account_type") != "user" or current.get("must_change_password")):
                return RedirectResponse(_oauth_redirect_url("link_session_expired"), status_code=303)
            if existing_identity and existing_identity.get("user_id") != current["id"]:
                return RedirectResponse(_oauth_redirect_url("identity_already_linked"), status_code=303)
            database.save_record("oauth_identities", identity_key, {
                "id": identity_key, "provider": provider, "subject_hash": hashlib.sha256(subject.encode()).hexdigest(),
                "user_id": current["id"], "tenant_id": tenant["id"], "linked_at": _now().isoformat(),
            })
            record_audit_event(current["email"], "oauth_identity_linked", "user", current["id"], {"provider": provider})
            return RedirectResponse(f"{os.getenv('CAMPAIGNNOVA_PUBLIC_WEB_URL', 'http://localhost:3000').rstrip('/')}/profile?linked={provider}", status_code=303)
        user = next((row for row in _accounts() if existing_identity and row.get("id") == existing_identity.get("user_id")), None)
        if not user:
            verified = identity.get("email_verified") is True or str(identity.get("email_verified", "")).casefold() == "true"
            if not email or not verified:
                return RedirectResponse(_oauth_completion_url(context, "email_not_verified"), status_code=303)
            user = _find_email(email)
        if not user:
            return RedirectResponse(_oauth_completion_url(context, "account_not_found"), status_code=303)
        if user.get("status") != "Active":
            return RedirectResponse(_oauth_completion_url(context, "account_inactive"), status_code=303)
        if user.get("must_change_password"):
            return RedirectResponse(_oauth_completion_url(context, "password_change_required"), status_code=303)
        if existing_identity and existing_identity.get("user_id") != user["id"]:
            return RedirectResponse(_oauth_completion_url(context, "identity_mismatch"), status_code=303)
        if not existing_identity:
            database.save_record("oauth_identities", identity_key, {
                "id": identity_key, "provider": provider, "subject_hash": hashlib.sha256(subject.encode()).hexdigest(),
                "user_id": user["id"], "tenant_id": tenant["id"], "linked_at": _now().isoformat(),
            })
        user["last_login_at"] = _now().isoformat()
        _save_user(user)
        response = RedirectResponse(_oauth_completion_url(context), status_code=303)
        _new_session(response, user)
        record_audit_event(user["email"], "signed_in_with_oauth", "user", user["id"], {"provider": provider})
        return response
    except Exception:
        return RedirectResponse(_oauth_completion_url(context, "oauth_failed"), status_code=303)


@router.post("/demo-login")
def demo_login(request: Request, response: Response):
    """Create a read-only session scoped to the seeded CampaignNova demo tenant."""
    if os.getenv("CAMPAIGNNOVA_ENV", "development").casefold() == "production" and os.getenv(
        "CAMPAIGNNOVA_DEMO_MODE", "false"
    ).casefold() != "true":
        raise HTTPException(status_code=404, detail="Demo access is not enabled")
    existing_token = request.cookies.get(SESSION_COOKIE)
    if existing_token:
        existing_session = next((row for row in database.list_records("auth_sessions", tenant_id="*")
                                 if row.get("id") == _token_hash(existing_token)), None)
        if (existing_session and existing_session.get("demo_guest") and not existing_session.get("revoked")
                and existing_session.get("tenant_id") == "campaignnova-demo"
                and _utc(existing_session["expires_at"]) > _now()):
            database.set_tenant("campaignnova-demo")
            guest = _request_user_from_demo("campaignnova-demo")
            return {"user": public_user(guest), "access": "read-only",
                    "modules": ["dashboard", "analytics-insights", "reports-exports", "predictive-intelligence", "ab-testing"]}
    # Guest access is read-only. Keep a high abuse ceiling so people sharing a
    # home, office, school, or proxy IP do not block each other from the demo.
    _rate_limit(_rate_key(request, "demo-login", "guest"), 1000, 900)
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
    if not re.fullmatch(r"[0-9]{7,15}", phone):
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
