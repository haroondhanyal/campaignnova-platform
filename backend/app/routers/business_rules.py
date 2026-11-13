"""Deterministic campaign eligibility rules. Evaluation is preview only."""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import database, store
from ..services.audit import record_audit_event

router = APIRouter(prefix="/business-rules", tags=["business-rules"])

FIELDS = {"monthly_value", "data_usage_gb", "churn_risk", "segment", "preferred_channel", "consent"}
OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains"}


class Condition(BaseModel):
    field: str
    operator: str = "eq"
    value: Any

    @field_validator("field")
    @classmethod
    def supported_field(cls, value: str) -> str:
        if value not in FIELDS:
            raise ValueError(f"field must be one of: {', '.join(sorted(FIELDS))}")
        return value

    @field_validator("operator")
    @classmethod
    def supported_operator(cls, value: str) -> str:
        if value not in OPS:
            raise ValueError(f"operator must be one of: {', '.join(sorted(OPS))}")
        return value


class RuleInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = ""
    conditions: list[Condition] = Field(default_factory=list)
    match: Literal["all", "any"] = "all"
    active: bool = False
    frequency_cap: int = Field(default=1, ge=1, le=20)
    cap_window_days: int = Field(default=7, ge=1, le=365)
    quiet_hours: dict[str, int] | None = None  # {start: 21, end: 8}, UTC hours

    @field_validator("quiet_hours")
    @classmethod
    def valid_quiet_hours(cls, value):
        if value is not None and (set(value) != {"start", "end"} or any(not isinstance(v, int) or v < 0 or v > 23 for v in value.values())):
            raise ValueError("quiet_hours must contain start and end UTC hours from 0 to 23")
        return value


def _rows():
    return database.list_records("business_rules")


def _rule(rule_id: str):
    item = next((r for r in _rows() if r["id"] == rule_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Business rule not found")
    return item


def _save(record):
    database.save_record("business_rules", record["id"], record)
    return record


@router.get("")
def list_rules():
    return _rows()


@router.post("", status_code=201)
def create_rule(payload: RuleInput):
    if any(r["name"].casefold() == payload.name.casefold() for r in _rows()):
        raise HTTPException(status_code=409, detail="A rule with this name already exists")
    now = datetime.now(timezone.utc).isoformat()
    row = _save({"id": f"rule-{uuid4().hex[:10]}", **payload.model_dump(mode="json"), "created_at": now, "updated_at": now})
    record_audit_event("local-user", "business_rule_created", "business_rule", row["id"], {"name": row["name"]})
    return row


@router.get("/{rule_id}")
def get_rule(rule_id: str):
    return _rule(rule_id)


@router.put("/{rule_id}")
def update_rule(rule_id: str, payload: RuleInput):
    current = _rule(rule_id)
    if any(r["id"] != rule_id and r["name"].casefold() == payload.name.casefold() for r in _rows()):
        raise HTTPException(status_code=409, detail="A rule with this name already exists")
    row = _save({**current, **payload.model_dump(mode="json"), "updated_at": datetime.now(timezone.utc).isoformat()})
    record_audit_event("local-user", "business_rule_updated", "business_rule", rule_id, {"name": row["name"]})
    return row


@router.patch("/{rule_id}/activation")
def set_activation(rule_id: str, active: bool):
    current = _rule(rule_id)
    row = _save({**current, "active": active, "updated_at": datetime.now(timezone.utc).isoformat()})
    record_audit_event("local-user", "business_rule_activation_changed", "business_rule", rule_id, {"active": active})
    return row


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str):
    _rule(rule_id)
    # Keep persistence operations behind the database abstraction.
    from ..database import connect
    with connect() as db:
        db.execute("DELETE FROM business_rules WHERE id = ?", (rule_id,))
    record_audit_event("local-user", "business_rule_deleted", "business_rule", rule_id, {"name": current["name"]})


def _matches(customer, condition: dict[str, Any]) -> bool:
    left, right = getattr(customer, condition["field"]), condition["value"]
    op = condition["operator"]
    if op == "eq": return left == right
    if op == "ne": return left != right
    if op == "contains": return str(right).casefold() in str(left).casefold()
    try:
        return {"gt": left > right, "gte": left >= right, "lt": left < right, "lte": left <= right}[op]
    except TypeError:
        return False


@router.post("/{rule_id}/evaluate/{customer_id}")
def evaluate_rule(rule_id: str, customer_id: str, at: datetime | None = None):
    rule = _rule(rule_id)
    customer = next((c for c in store.get_customers() if c.id == customer_id), None)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    checks = []
    checks.append(("rule_inactive", bool(rule["active"])))
    checks.append(("no_consent", bool(customer.consent)))
    conds = rule.get("conditions", [])
    condition_result = (all if rule.get("match", "all") == "all" else any)(_matches(customer, c) for c in conds) if conds else True
    checks.append(("conditions_not_met", condition_result))
    quiet = rule.get("quiet_hours")
    quiet_now = bool(quiet and ((quiet["start"] <= now.hour < quiet["end"]) if quiet["start"] < quiet["end"] else (now.hour >= quiet["start"] or now.hour < quiet["end"])))
    checks.append(("quiet_hours", not quiet_now))
    since = now.timestamp() - rule.get("cap_window_days", 7) * 86400
    hits = sum(1 for run in database.list_records("execution_runs") if _timestamp(run.get("created_at")) >= since
               for contact in run.get("customers", []) if contact.get("customer_id") == customer_id and contact.get("attempts", 0) > 0)
    checks.append(("frequency_cap", hits < rule.get("frequency_cap", 1)))
    failed = [reason for reason, passed in checks if not passed]
    return {"rule_id": rule_id, "customer_id": customer_id, "eligible": not failed, "suppressed": bool(failed),
            "suppression_reasons": failed, "checks": {reason: passed for reason, passed in checks},
            "evaluated_at": now.isoformat(), "delivery": "preview_only"}


def _timestamp(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return 0
