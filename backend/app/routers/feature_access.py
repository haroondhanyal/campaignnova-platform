"""Tenant-scoped module requests, department access and approval workflows."""
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import database
from ..services.audit import record_audit_event
from . import authentication as auth

router = APIRouter(prefix="/feature-access", tags=["feature access"])


class FeatureRequestCreate(BaseModel):
    module: str
    reason: str = Field(default="", max_length=500)

    @field_validator("module")
    @classmethod
    def known_module(cls, value: str) -> str:
        if value not in auth.MODULE_TITLES:
            raise ValueError("Choose a listed CampaignNova feature")
        return value


class FeatureDecision(BaseModel):
    decision: str
    note: str = Field(default="", max_length=500)

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, value: str) -> str:
        if value not in {"Approved", "Rejected"}:
            raise ValueError("Decision must be Approved or Rejected")
        return value


class DepartmentAccess(BaseModel):
    modules: list[str]

    @field_validator("modules")
    @classmethod
    def valid_modules(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(auth.MODULE_KEYS)
        if unknown:
            raise ValueError("Unknown module in department access")
        return list(dict.fromkeys(value))


def _rows() -> list[dict]:
    return database.list_records("feature_requests")


def _can_review(user: dict, department: str | None = None) -> bool:
    if user.get("role") in auth.ADMIN_ROLES:
        return True
    return user.get("role") == "Department Manager" and user.get("department") == department


@router.get("/catalog")
def catalog(current: dict = Depends(auth.require_user)):
    tenant = current.get("tenant_id") or database.current_tenant()
    enabled = auth._enabled_modules(tenant)
    department = current.get("department", "")
    department_enabled = sorted(auth._department_enabled_modules(department, tenant))
    return {
        "company": current.get("organization_name", "Company"),
        "department": department,
        "enabled_modules": enabled,
        "department_modules": department_enabled,
        "can_manage_company": current.get("role") in auth.ADMIN_ROLES,
        "can_manage_department": _can_review(current, department),
        "is_demo_guest": current.get("is_demo_guest", False),
        "modules": [{"key": key, "title": title, "company_enabled": key in enabled,
                     "department_enabled": key in department_enabled,
                     "available_to_user": auth._user_can_access_module(current, key)}
                    for key, title in auth.MODULE_TITLES.items()],
        "departments": list(auth.DEPARTMENTS),
    }


@router.get("/departments/{department}")
def get_department_access(department: str, current: dict = Depends(auth.require_user)):
    if department not in auth.DEPARTMENTS:
        raise HTTPException(status_code=404, detail="Department not found")
    if not _can_review(current, department):
        raise HTTPException(status_code=403, detail="Only the company admin or this department manager can manage its access")
    settings = auth._workspace_settings()
    customized = settings.get("department_module_access", {}).get(department)
    modules = customized if isinstance(customized, list) else sorted(auth.DEPARTMENT_MODULES.get(department, set()))
    return {"department": department, "modules": modules, "company_modules": auth._enabled_modules()}


@router.put("/departments/{department}")
def save_department_access(department: str, payload: DepartmentAccess, current: dict = Depends(auth.require_user)):
    if department not in auth.DEPARTMENTS:
        raise HTTPException(status_code=404, detail="Department not found")
    if not _can_review(current, department):
        raise HTTPException(status_code=403, detail="Only the company admin or this department manager can manage its access")
    enabled = set(auth._enabled_modules())
    if not set(payload.modules).issubset(enabled):
        raise HTTPException(status_code=422, detail="A department can only use features enabled for its company")
    settings = auth._workspace_settings()
    department_access = dict(settings.get("department_module_access", {}))
    department_access[department] = payload.modules
    settings.update({"id": "workspace-defaults", "department_module_access": department_access,
                     "updated_at": datetime.now(timezone.utc).isoformat()})
    database.save_record("workspace_settings", "workspace-defaults", settings)
    # An explicit custom department policy is also the user's grant ceiling.
    for user in auth._accounts():
        if user.get("department") == department and isinstance(user.get("module_access"), list):
            user["module_access"] = [module for module in user["module_access"] if module in payload.modules]
            auth._save_user(user)
    record_audit_event(current["email"], "department_feature_access_updated", "department", department,
                       {"modules": payload.modules})
    return {"department": department, "modules": payload.modules}


@router.get("/requests")
def list_requests(current: dict = Depends(auth.require_user)):
    rows = sorted(_rows(), key=lambda row: row["created_at"], reverse=True)
    if current.get("role") in auth.ADMIN_ROLES:
        return rows
    if current.get("role") == "Department Manager":
        return [row for row in rows if row.get("department") == current.get("department")]
    return [row for row in rows if row.get("requester_id") == current.get("id")]


@router.post("/requests", status_code=201)
def create_request(payload: FeatureRequestCreate, current: dict = Depends(auth.require_user)):
    tenant = current.get("tenant_id") or database.current_tenant()
    if auth._user_can_access_module(current, payload.module):
        raise HTTPException(status_code=409, detail="This feature is already available to your account")
    pending = next((row for row in _rows() if row.get("requester_id") == current["id"]
                    and row.get("module") == payload.module and row.get("status") == "Pending"), None)
    if pending:
        raise HTTPException(status_code=409, detail="You already have a pending request for this feature")
    row = {"id": f"ftr-{uuid4().hex[:12]}", "requester_id": current["id"],
           "requester": current["display_name"], "email": current["email"],
           "department": current["department"], "module": payload.module,
           "module_title": auth.MODULE_TITLES[payload.module], "reason": payload.reason.strip(),
           "status": "Pending", "created_at": datetime.now(timezone.utc).isoformat(),
           "decision_by": None, "decision_note": None, "decided_at": None}
    database.save_record("feature_requests", row["id"], row)
    record_audit_event(current["email"], "feature_access_requested", "feature", payload.module,
                       {"request_id": row["id"], "department": row["department"]})
    return row


@router.post("/requests/{request_id}/decision")
def decide_request(request_id: str, payload: FeatureDecision, current: dict = Depends(auth.require_user)):
    row = next((item for item in _rows() if item["id"] == request_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="Feature request not found")
    if not _can_review(current, row["department"]):
        raise HTTPException(status_code=403, detail="Only the company admin or that department manager can review this request")
    if row["status"] != "Pending":
        raise HTTPException(status_code=409, detail="This request has already been reviewed")
    if row.get("requester_id") == current.get("id"):
        raise HTTPException(status_code=403, detail="You cannot approve your own feature request")
    if payload.decision == "Approved":
        settings = auth._workspace_settings()
        company_modules = list(auth._enabled_modules())
        if row["module"] not in company_modules:
            if current.get("role") not in auth.ADMIN_ROLES:
                raise HTTPException(status_code=409, detail="A company Super Admin must enable this feature before department approval")
            company_modules.append(row["module"])
        departments = dict(settings.get("department_module_access", {}))
        current_modules = departments.get(row["department"])
        if not isinstance(current_modules, list):
            current_modules = sorted(auth.DEPARTMENT_MODULES.get(row["department"], set()))
        departments[row["department"]] = list(dict.fromkeys([*current_modules, row["module"]]))
        settings.update({"id": "workspace-defaults", "enabled_modules": company_modules, "department_module_access": departments,
                         "updated_at": datetime.now(timezone.utc).isoformat()})
        database.save_record("workspace_settings", "workspace-defaults", settings)
        target = next((user for user in auth._accounts() if user.get("id") == row["requester_id"]), None)
        if target and isinstance(target.get("module_access"), list) and row["module"] not in target["module_access"]:
            target["module_access"].append(row["module"])
            auth._save_user(target)
    row.update({"status": payload.decision, "decision_by": current["email"],
                "decision_note": payload.note.strip(), "decided_at": datetime.now(timezone.utc).isoformat()})
    database.save_record("feature_requests", row["id"], row)
    record_audit_event(current["email"], "feature_access_request_decided", "feature", row["module"],
                       {"request_id": row["id"], "decision": row["status"], "department": row["department"]})
    return row
