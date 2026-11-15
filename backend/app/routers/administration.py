"""Administrator-only account directory and workspace configuration."""
import re
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from .. import database
from ..services.audit import record_audit_event
from ..services import gemini
from . import authentication as auth

router = APIRouter(prefix="/admin", tags=["administration"])
DEFAULT_SETTINGS = {"id": "workspace-defaults", "workspace_name": "CampaignNova", "timezone": "UTC",
                    "currency": "USD", "date_format": "YYYY-MM-DD", "default_channel": "SMS", "updated_at": None}


class UserCreate(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone_country_code: str = Field(pattern=r"^\+[1-9]\d{0,3}$")
    phone_number: str = Field(min_length=7, max_length=18)
    department: str
    role: str
    temporary_password: str
    module_access: list[str] | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid work email")
        return value

    @field_validator("department")
    @classmethod
    def valid_department(cls, value: str) -> str:
        if value not in auth.DEPARTMENTS:
            raise ValueError("Choose a listed department")
        return value

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in auth.ROLES:
            raise ValueError("Choose a listed role")
        return value

    @field_validator("temporary_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return auth._validate_password(value)

    @field_validator("module_access")
    @classmethod
    def valid_module_access(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (len(value) != len(set(value)) or any(module not in auth.MODULE_TITLES for module in value)):
            raise ValueError("Choose valid, unique workspace modules")
        return value

    @model_validator(mode="after")
    def role_matches_department(self):
        if not auth.valid_role_department(self.role, self.department):
            raise ValueError("This role is not available in the selected department")
        return self


class UserUpdate(BaseModel):
    role: str | None = None
    department: str | None = None
    status: Literal["Active", "Pending Approval", "Disabled"] | None = None
    module_access: list[str] | None = None

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str | None) -> str | None:
        if value is not None and value not in auth.ROLES:
            raise ValueError("Choose a listed role")
        return value

    @field_validator("department")
    @classmethod
    def valid_department(cls, value: str | None) -> str | None:
        if value is not None and value not in auth.DEPARTMENTS:
            raise ValueError("Choose a listed department")
        return value

    @field_validator("module_access")
    @classmethod
    def valid_module_access(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (len(value) != len(set(value)) or any(module not in auth.MODULE_TITLES for module in value)):
            raise ValueError("Choose valid, unique workspace modules")
        return value

    @model_validator(mode="after")
    def role_matches_department(self):
        if self.role and self.department and not auth.valid_role_department(self.role, self.department):
            raise ValueError("This role is not available in the selected department")
        return self


class CompanyCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=120)
    super_admin_name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=254)
    phone_country_code: str = Field(pattern=r"^\+[1-9]\d{0,3}$")
    phone_number: str = Field(min_length=7, max_length=18)
    temporary_password: str
    logo_data: str = Field(min_length=30)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().casefold()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid company email")
        return value

    @field_validator("temporary_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return auth._validate_password(value)

    @field_validator("logo_data")
    @classmethod
    def valid_logo(cls, value: str) -> str:
        image = auth._validate_avatar(value)
        if not image:
            raise ValueError("Upload the company logo to create a branded workspace")
        if len(image.split(",", 1)[1]) * 3 // 4 > 2 * 1024 * 1024:
            raise ValueError("Company logo must be 2 MB or smaller")
        return image

    @field_validator("company_name", "super_admin_name")
    @classmethod
    def clean_names(cls, value: str) -> str:
        return value.strip()


class WorkspaceSettings(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=100)
    timezone: str = Field(min_length=2, max_length=80)
    currency: Literal["PKR", "USD", "EUR", "GBP"] = "USD"
    date_format: Literal["YYYY-MM-DD", "DD MMM YYYY", "MM/DD/YYYY"] = "YYYY-MM-DD"
    default_channel: Literal["SMS", "WhatsApp", "USSD", "Push", "Email", "In-App"] = "SMS"
    enabled_modules: list[str] = Field(default_factory=lambda: list(auth.MODULE_KEYS))
    department_module_access: dict[str, list[str]] = Field(default_factory=dict)
    logo_data: str | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        value = value.strip()
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError:
            raise ValueError("Enter a valid IANA timezone such as Asia/Karachi") from None
        return value

    @field_validator("workspace_name")
    @classmethod
    def clean_workspace_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("enabled_modules")
    @classmethod
    def valid_enabled_modules(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)) or any(module not in auth.MODULE_TITLES for module in value):
            raise ValueError("Choose valid, unique workspace modules")
        if not {"settings", "user-roles", "feature-access"}.issubset(value):
            raise ValueError("System settings, user administration, and feature requests must remain enabled")
        return list(dict.fromkeys(["dashboard", *value]))

    @field_validator("department_module_access")
    @classmethod
    def valid_department_access(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        for department, modules in value.items():
            if department not in auth.DEPARTMENTS or not set(modules).issubset(auth.MODULE_KEYS):
                raise ValueError("Choose known departments and CampaignNova modules")
        return value

    @field_validator("logo_data")
    @classmethod
    def valid_logo(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        image = auth._validate_avatar(value)
        if len(image.split(",", 1)[1]) * 3 // 4 > 2 * 1024 * 1024:
            raise ValueError("Company logo must be 2 MB or smaller")
        return image


def _users() -> list[dict]:
    return auth._accounts()


@router.get("/roles")
def list_roles(_: dict = Depends(auth.require_admin)):
    return {"enforcement": "enabled", "roles": [
        {"name": role, "description": role.replace("&", "and"),
         "departments": sorted(auth.ROLE_DEPARTMENTS.get(role, set()))}
        for role in auth.ROLES
    ], "departments": list(auth.DEPARTMENTS),
        "modules": [{"key": key, "title": title} for key, title in auth.MODULE_TITLES.items()],
        "enabled_modules": auth._enabled_modules(),
            "department_modules": {department: sorted(auth._department_enabled_modules(department)) for department in auth.DEPARTMENTS},
        "notice": "Company modules and account-level access are enforced by the API."}


@router.get("/users")
def list_users(_: dict = Depends(auth.require_admin)):
    return {"enforcement": "enabled", "users": [auth.public_user(user) for user in _users()]}


@router.get("/overview")
def super_admin_overview(_: dict = Depends(auth.require_super_admin)):
    users = _users()
    now = datetime.now(timezone.utc)
    recent_cutoff = now - timedelta(minutes=5)
    online: dict[str, str] = {}
    last_seen_by_user: dict[str, str] = {}
    user_ids = {user["id"] for user in users}
    active_user_ids = {user["id"] for user in users if user.get("status") == "Active"}
    for session in database.list_records("auth_sessions"):
        user_id = session.get("user_id")
        last_seen = session.get("last_seen_at")
        if user_id not in user_ids or session.get("revoked") or not last_seen:
            continue
        try:
            seen_at = datetime.fromisoformat(last_seen.replace("Z", "+00:00"))
            expires_at = datetime.fromisoformat(session["expires_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError):
            continue
        seen_text = seen_at.isoformat()
        previous_seen = last_seen_by_user.get(user_id)
        if not previous_seen or seen_text > previous_seen:
            last_seen_by_user[user_id] = seen_text
        if user_id in active_user_ids and seen_at >= recent_cutoff and expires_at > now:
            online[user_id] = last_seen_by_user[user_id]
    return {
        "total_users": len(users),
        "active_users": sum(user.get("status") == "Active" for user in users),
        "inactive_users": sum(user.get("status") == "Disabled" for user in users),
        "pending_users": sum(user.get("status") == "Pending Approval" for user in users),
        "online_users": len(online),
        "online_window_minutes": 5,
        "users": [{**auth.public_user(user), "online": user["id"] in online,
                   "last_seen_at": last_seen_by_user.get(user["id"])} for user in users],
    }


@router.post("/companies", status_code=201)
def create_company(payload: CompanyCreate, current: dict = Depends(auth.require_super_admin)):
    slug = re.sub(r"[^a-z0-9]+", "-", payload.company_name.casefold()).strip("-")[:70].strip("-")
    if len(slug) < 2 or slug == "campaignnova-demo":
        raise HTTPException(status_code=422, detail="Enter a company name that can identify its workspace")
    if database.global_record("workspace_tenants", slug):
        raise HTTPException(status_code=409, detail="A company workspace already uses this name or workspace code")
    try:
        auth._validate_phone_number(payload.phone_number, payload.phone_country_code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    now = datetime.now(timezone.utc).isoformat()
    tenant = {"id": slug, "slug": slug, "name": payload.company_name,
              "created_at": now, "created_by": current["id"], "tenant_id": "__global__"}
    database.save_record("workspace_tenants", slug, tenant)
    enabled_modules = list(auth.DEFAULT_ENABLED_MODULES)
    database.save_record("workspace_settings", "workspace-defaults", {
        **DEFAULT_SETTINGS, "id": "workspace-defaults", "workspace_name": payload.company_name,
        "enabled_modules": enabled_modules, "department_module_access": {},
        "logo_data": payload.logo_data, "updated_at": now, "tenant_id": slug,
    })
    super_admin = {
        "id": f"usr-{uuid4().hex[:12]}", "account_type": "user", "display_name": payload.super_admin_name,
        "tenant_id": slug, "organization_name": payload.company_name, "organization_slug": slug,
        "email": payload.email, "phone_country_code": payload.phone_country_code,
        "phone_number": payload.phone_number, "department": "Administration", "role": "Super Admin",
        "status": "Active", "must_change_password": True, "module_access": None,
        "avatar_data": None, "avatar_mime": None,
        "password_hash": auth._password_hash(payload.temporary_password), "created_at": now, "updated_at": now,
    }
    database.save_record("workspace_users", super_admin["id"], super_admin)
    record_audit_event(current["email"], "super_admin_created_company_workspace", "workspace", slug,
                       {"company_name": payload.company_name, "first_super_admin": payload.email})
    return {"workspace": {"name": tenant["name"], "slug": slug,
                           "logo_url": f"/api/auth/workspaces/{slug}/logo" if payload.logo_data else auth.COMPANY_LOGOS.get(slug)},
            "super_admin": auth.public_user(super_admin)}


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, current: dict = Depends(auth.require_admin)):
    if payload.module_access is not None and current.get("role") != "Super Admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can set account-level module access")
    if payload.module_access is not None and not set(payload.module_access).issubset(auth._enabled_modules()):
        raise HTTPException(status_code=422, detail="Account access can only include company-enabled modules")
    if auth._find_email(payload.email):
        raise HTTPException(status_code=409, detail="A workspace account already uses this email")
    if payload.role == "Super Admin" and current.get("role") != "Super Admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can create another Super Admin")
    now = datetime.now(timezone.utc).isoformat()
    user = {"id": f"usr-{uuid4().hex[:12]}", "account_type": "user", "display_name": payload.display_name.strip(),
            "email": payload.email, "phone_country_code": payload.phone_country_code,
            "phone_number": payload.phone_number, "department": payload.department,
            "role": payload.role, "status": "Active", "must_change_password": True,
            "module_access": payload.module_access,
            "avatar_data": None, "avatar_mime": None, "password_hash": auth._password_hash(payload.temporary_password),
            "created_at": now, "updated_at": now}
    if not re.fullmatch(r"[0-9]{7,15}", user["phone_number"]):
        raise HTTPException(status_code=422, detail="Enter a phone number using 7–15 digits")
    try:
        auth._validate_phone_number(user["phone_number"], user["phone_country_code"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    auth._save_user(user)
    record_audit_event(current["email"], "administrator_created_account", "user", user["id"],
                       {"department": user["department"], "role": user["role"]})
    return auth.public_user(user)


@router.patch("/users/{user_id}")
def update_user(user_id: str, payload: UserUpdate, current: dict = Depends(auth.require_admin)):
    user = next((row for row in _users() if row["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    changes = payload.model_dump(exclude_unset=True)
    if "module_access" in changes:
        if current.get("role") != "Super Admin":
            raise HTTPException(status_code=403, detail="Only a Super Admin can change account-level module access")
        if changes["module_access"] is not None and not set(changes["module_access"]).issubset(auth._enabled_modules()):
            raise HTTPException(status_code=422, detail="Account access can only include company-enabled modules")
        if user["id"] == current["id"] and user.get("role") == "Super Admin" and changes["module_access"] is not None and not {"settings", "user-roles"}.issubset(changes["module_access"]):
            raise HTTPException(status_code=422, detail="Keep Settings and User & Role Management on your own Super Admin account so you can recover workspace access")
    if not auth.valid_role_department(changes.get("role", user["role"]), changes.get("department", user["department"])):
        raise HTTPException(status_code=422, detail="This role is not available in the selected department")
    if user["id"] == current["id"] and changes.get("status") == "Disabled":
        raise HTTPException(status_code=400, detail="You cannot disable your own active session")
    if changes.get("role") == "Super Admin" and current.get("role") != "Super Admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can assign that role")
    remaining_super_admins = [row for row in _users() if row.get("role") == "Super Admin" and row.get("status") == "Active"]
    if user.get("role") == "Super Admin" and user.get("status") == "Active" and (
        changes.get("status") == "Disabled" or ("role" in changes and changes["role"] != "Super Admin")
    ) and len(remaining_super_admins) <= 1:
        raise HTTPException(status_code=400, detail="At least one active Super Admin must remain")
    user.update(changes)
    user["updated_at"] = datetime.now(timezone.utc).isoformat()
    auth._save_user(user)
    record_audit_event(current["email"], "administrator_updated_account", "user", user_id,
                       {**{key: user[key] for key in ("role", "department", "status")},
                        **({"module_access": user.get("module_access")} if "module_access" in changes else {})})
    return auth.public_user(user)


@router.get("/settings")
def get_settings():
    saved = next(iter(database.list_records("workspace_settings")), None)
    tenant = next((item for item in database.list_records("workspace_tenants", tenant_id="*")
                   if item.get("id") == database.current_tenant()), None)
    defaults = {**DEFAULT_SETTINGS, "workspace_name": (tenant or {}).get("name", "CampaignNova"),
                "enabled_modules": auth._enabled_modules(), "department_module_access": {}, "logo_data": None}
    saved = dict(saved or {})
    slug = (tenant or {}).get("slug", "")
    return {**defaults, **saved, "enabled_modules": auth._enabled_modules(),
            "organization_slug": slug,
            "organization_logo_url": f"/api/auth/workspaces/{slug}/logo" if saved.get("logo_data") else None,
            "runtime": {"database": "SQLite development store", "gemini_configured": gemini.configured(),
                        "live_channel_providers": 0, "authentication": "session-cookie-rbac"}}


@router.put("/settings")
def save_settings(payload: WorkspaceSettings, current: dict = Depends(auth.require_admin)):
    previous = auth._workspace_settings()
    submitted = payload.model_dump()
    enabled = set(submitted["enabled_modules"]) | {"dashboard"}
    submitted["department_module_access"] = {
        department: [module for module in modules if module in enabled]
        for department, modules in submitted["department_module_access"].items()
    }
    row = {**previous, "id": DEFAULT_SETTINGS["id"], **submitted, "updated_at": datetime.now(timezone.utc).isoformat()}
    database.save_record("workspace_settings", row["id"], row)
    for user in auth._accounts():
        if isinstance(user.get("module_access"), list):
            user["module_access"] = [module for module in user["module_access"] if module in enabled]
            auth._save_user(user)
    tenant = next((item for item in database.list_records("workspace_tenants", tenant_id="*")
                   if item.get("id") == database.current_tenant()), None)
    if tenant:
        database.save_record("workspace_tenants", tenant["id"], {**tenant, "name": row["workspace_name"]})
    record_audit_event(current["email"], "workspace_settings_updated", "workspace", row["id"],
                       {"timezone": row["timezone"], "currency": row["currency"],
                        "enabled_modules": row["enabled_modules"]})
    return get_settings()
