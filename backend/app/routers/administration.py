"""Administrator-only account directory and workspace configuration."""
import re
from datetime import datetime, timezone
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

    @model_validator(mode="after")
    def role_matches_department(self):
        if not auth.valid_role_department(self.role, self.department):
            raise ValueError("This role is not available in the selected department")
        return self


class UserUpdate(BaseModel):
    role: str | None = None
    department: str | None = None
    status: Literal["Active", "Pending Approval", "Disabled"] | None = None

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

    @model_validator(mode="after")
    def role_matches_department(self):
        if self.role and self.department and not auth.valid_role_department(self.role, self.department):
            raise ValueError("This role is not available in the selected department")
        return self


class WorkspaceSettings(BaseModel):
    workspace_name: str = Field(min_length=2, max_length=100)
    timezone: str = Field(min_length=2, max_length=80)
    currency: Literal["PKR", "USD", "EUR", "GBP"] = "USD"
    date_format: Literal["YYYY-MM-DD", "DD MMM YYYY", "MM/DD/YYYY"] = "YYYY-MM-DD"
    default_channel: Literal["SMS", "WhatsApp", "USSD", "Push", "Email", "In-App"] = "SMS"

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


def _users() -> list[dict]:
    return auth._accounts()


@router.get("/roles")
def list_roles(_: dict = Depends(auth.require_admin)):
    return {"enforcement": "enabled", "roles": [
        {"name": role, "description": role.replace("&", "and"),
         "departments": sorted(auth.ROLE_DEPARTMENTS.get(role, set()))}
        for role in auth.ROLES
    ], "departments": list(auth.DEPARTMENTS), "notice": "Accounts, department access, and role permissions are enforced by the API."}


@router.get("/users")
def list_users(_: dict = Depends(auth.require_admin)):
    return {"enforcement": "enabled", "users": [auth.public_user(user) for user in _users()]}


@router.post("/users", status_code=201)
def create_user(payload: UserCreate, current: dict = Depends(auth.require_admin)):
    if auth._find_email(payload.email):
        raise HTTPException(status_code=409, detail="A workspace account already uses this email")
    if payload.role == "Super Admin" and current.get("role") != "Super Admin":
        raise HTTPException(status_code=403, detail="Only a Super Admin can create another Super Admin")
    now = datetime.now(timezone.utc).isoformat()
    user = {"id": f"usr-{uuid4().hex[:12]}", "account_type": "user", "display_name": payload.display_name.strip(),
            "email": payload.email, "phone_country_code": payload.phone_country_code,
            "phone_number": re.sub(r"[\s()\-]", "", payload.phone_number), "department": payload.department,
            "role": payload.role, "status": "Active", "must_change_password": True,
            "avatar_data": None, "avatar_mime": None, "password_hash": auth._password_hash(payload.temporary_password),
            "created_at": now, "updated_at": now}
    if not re.fullmatch(r"\d{7,15}", user["phone_number"]):
        raise HTTPException(status_code=422, detail="Enter a phone number using 7–15 digits")
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
                       {key: user[key] for key in ("role", "department", "status")})
    return auth.public_user(user)


@router.get("/settings")
def get_settings():
    saved = next(iter(database.list_records("workspace_settings")), None)
    tenant = next((item for item in database.list_records("workspace_tenants", tenant_id="*")
                   if item.get("id") == database.current_tenant()), None)
    defaults = {**DEFAULT_SETTINGS, "workspace_name": (tenant or {}).get("name", "CampaignNova")}
    saved = dict(saved or {})
    if saved.get("workspace_name", "").casefold().startswith("ptcl "):
        saved.pop("workspace_name", None)
    return {**defaults, **saved,
            "runtime": {"database": "SQLite development store", "gemini_configured": gemini.configured(),
                        "live_channel_providers": 0, "authentication": "session-cookie-rbac"}}


@router.put("/settings")
def save_settings(payload: WorkspaceSettings, current: dict = Depends(auth.require_settings_admin)):
    row = {"id": DEFAULT_SETTINGS["id"], **payload.model_dump(), "updated_at": datetime.now(timezone.utc).isoformat()}
    database.save_record("workspace_settings", row["id"], row)
    record_audit_event(current["email"], "workspace_settings_updated", "workspace", row["id"],
                       {"timezone": row["timezone"], "currency": row["currency"]})
    return get_settings()
