"""Local, deterministic campaign execution simulator. It never contacts a provider."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import database, store
from ..services.segmentation import segment_members
from ..services.audit import record_audit_event

router = APIRouter(prefix="/execution", tags=["execution"])
CHANNELS = {"SMS", "WhatsApp", "USSD", "Push", "Email", "In-App"}


class StartRun(BaseModel):
    campaign_id: str
    idempotency_key: str = Field(min_length=8, max_length=120)
    batch_size: int = Field(default=25, ge=1, le=500)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)


def _all_runs():
    return database.list_records("execution_runs")


def _save(run):
    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    database.save_record("execution_runs", run["id"], run)
    return run


def _get(run_id):
    run = next((item for item in _all_runs() if item["id"] == run_id), None)
    if not run:
        raise HTTPException(404, "Execution run not found")
    return run


def _process(run, retry=False):
    if run["status"] == "Paused":
        return run
    items = run["customers"]
    if retry:
        pending = [x for x in items if x["status"] == "Simulated Failed" and x["attempts"] < 3]
        limit = min(run["batch_size"], run["rate_limit_per_minute"])
        chosen = pending[:limit]
    else:
        pending = [x for x in items if x["status"] == "Queued"]
        limit = min(run["batch_size"], run["rate_limit_per_minute"])
        chosen = pending[:limit]
    run["batch_number"] += 1
    now = datetime.now(timezone.utc).isoformat()
    # The local adapter is deterministic and intentionally marks cus-1002 as a simulated failure.
    for item in chosen:
        item["attempts"] += 1
        failed = item["customer_id"].endswith("2")
        item["status"] = "Simulated Failed" if failed else "Simulated Delivered"
        item["last_attempt_at"] = now
        item["result"] = "SIMULATION: deterministic adapter failure" if failed else "SIMULATION: accepted by local adapter; no message sent"
        item["history"].append({"attempt": item["attempts"], "status": item["status"], "at": now, "mode": "SIMULATION"})
    if not retry:
        remains = any(x["status"] == "Queued" for x in items)
        run["status"] = "Queued" if remains else "Completed"
    run["summary"] = _counts(run)
    return _save(run)


def _counts(run):
    rows = run["customers"]
    failed = sum(x["status"] == "Simulated Failed" for x in rows)
    return {"targeted": len(rows), "queued": sum(x["status"] == "Queued" for x in rows),
            "simulated_delivered": sum(x["status"] == "Simulated Delivered" for x in rows),
            "failed": failed, "dead_letter": sum(x["status"] == "Simulated Failed" and x["attempts"] >= 3 for x in rows),
            "consent_excluded": run.get("consent_excluded", 0), "rule_excluded": run.get("rule_excluded", 0)}


def _rules_allow(customer, rules, runs, now):
    """Apply active global rules to simulation eligibility; never deliver."""
    for rule in rules:
        conditions = rule.get("conditions", [])
        results = []
        for condition in conditions:
            field, op, expected = condition["field"], condition["operator"], condition["value"]
            value = customer.segment if field == "segment" else getattr(customer, field, None)
            if op == "eq": passed = value == expected
            elif op == "ne": passed = value != expected
            elif op == "contains": passed = str(expected).casefold() in str(value).casefold()
            else:
                try: passed = {"gt": value > expected, "gte": value >= expected, "lt": value < expected, "lte": value <= expected}[op]
                except (TypeError, KeyError): passed = False
            results.append(passed)
        if conditions and not ((all(results) if rule.get("match") == "all" else any(results))):
            return False
        quiet = rule.get("quiet_hours")
        if quiet:
            hour = now.hour
            start, end = quiet["start"], quiet["end"]
            if (start <= hour < end) if start < end else (hour >= start or hour < end):
                return False
        since = now.timestamp() - rule.get("cap_window_days", 7) * 86400
        contacts = sum(1 for run in runs if _run_timestamp(run.get("created_at")) >= since
                       for item in run.get("customers", [])
                       if item.get("customer_id") == customer.id and item.get("attempts", 0) > 0)
        if contacts >= rule.get("frequency_cap", 1):
            return False
    return True


def _run_timestamp(value):
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError): return 0


@router.get("/runs")
def list_runs():
    return list(reversed(_all_runs()))


@router.post("/runs")
def start_run(payload: StartRun):
    existing = next((r for r in _all_runs() if r.get("idempotency_key") == payload.idempotency_key), None)
    if existing:
        if existing["campaign_id"] != payload.campaign_id:
            raise HTTPException(409, "Idempotency key already belongs to another campaign")
        return existing
    campaign = next((c for c in store.get_campaigns() if c.id == payload.campaign_id), None)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status not in {"Approved", "Scheduled", "Running"}:
        raise HTTPException(409, "Campaign must be approved, scheduled, or running before simulation")
    if campaign.channel not in CHANNELS:
        raise HTTPException(422, "Campaign channel has no simulation adapter")
    target = list(store.get_customers())
    if campaign.segment_id:
        segment = next((s for s in store.get_segments() if s.id == campaign.segment_id), None)
        if not segment:
            raise HTTPException(422, "Campaign segment was not found")
        target = segment_members(segment, target)
    excluded = sum(not customer.consent or customer.subscription_status != "Active" for customer in target)
    base_eligible = [c for c in target if c.consent and c.subscription_status == "Active"]
    now_dt = datetime.now(timezone.utc)
    active_rules = [rule for rule in database.list_records("business_rules") if rule.get("active")]
    prior_runs = _all_runs()
    eligible = [c for c in base_eligible if _rules_allow(c, active_rules, prior_runs, now_dt)]
    rule_excluded = len(base_eligible) - len(eligible)
    if not eligible:
        raise HTTPException(422, "No active, consented customers are eligible for this simulation")
    now = now_dt.isoformat()
    run = {"id": f"run-{uuid4().hex[:10]}", "campaign_id": campaign.id, "campaign_name": campaign.name,
           "channel": campaign.channel, "mode": "SIMULATION", "status": "Queued", "idempotency_key": payload.idempotency_key,
           "batch_size": payload.batch_size, "rate_limit_per_minute": payload.rate_limit_per_minute, "batch_number": 0,
           "consent_excluded": excluded, "rule_excluded": rule_excluded, "created_at": now, "updated_at": now,
           "customers": [{"customer_id": c.id, "identifier": c.identifier, "status": "Queued", "attempts": 0,
                          "result": "Awaiting local simulation", "history": []} for c in eligible]}
    run["summary"] = _counts(run)
    database.save_record("execution_runs", run["id"], run)
    record_audit_event("local-simulator", "execution_simulated", "campaign", campaign.id,
                       {"run_id": run["id"], "mode": "SIMULATION", "targeted": len(eligible), "consent_excluded": excluded})
    return _process(run)


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return _get(run_id)


@router.post("/runs/{run_id}/pause")
def pause_run(run_id: str):
    run = _get(run_id)
    if run["status"] == "Queued":
        run["status"] = "Paused"
    saved = _save(run)
    record_audit_event("local-simulator", "execution_paused", "execution_run", run_id, {"status": saved["status"]})
    return saved


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str):
    run = _get(run_id)
    if run["status"] == "Paused":
        run["status"] = "Queued"
    if run["status"] == "Queued":
        saved = _process(run)
        record_audit_event("local-simulator", "execution_resumed", "execution_run", run_id, {"status": saved["status"]})
        return saved
    return run


@router.post("/runs/{run_id}/retry")
def retry_run(run_id: str):
    run = _get(run_id)
    if run["status"] == "Paused":
        raise HTTPException(409, "Resume the run before retrying")
    if not any(x["status"] == "Simulated Failed" and x["attempts"] < 3 for x in run["customers"]):
        raise HTTPException(409, "No retryable simulated failures remain")
    saved = _process(run, retry=True)
    record_audit_event("local-simulator", "execution_retried", "execution_run", run_id, {"summary": saved["summary"]})
    return saved
