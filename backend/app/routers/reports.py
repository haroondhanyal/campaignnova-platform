"""Observed-data report catalog and persisted scheduling metadata (no scheduler)."""
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import database, store
from ..services.audit import record_audit_event
from .authentication import require_user, ADMIN_ROLES

router = APIRouter(prefix="/reports", tags=["reports"])

DEFINITIONS = [
    {"id": "campaign-performance", "name": "Campaign performance", "description": "Campaign status, reached, conversions, observed revenue, and budget.", "data_basis": "Synthetic development campaign records; zero values are kept as recorded."},
    {"id": "channel-performance", "name": "Channel performance", "description": "Observed campaign reach and conversion totals by channel.", "data_basis": "Aggregated from synthetic campaign records; not attribution or causal lift."},
    {"id": "customer-cohorts", "name": "Customer cohorts", "description": "Sample profile counts and averages grouped by current segment.", "data_basis": "Synthetic customer sample only; not the segment estimate totals."},
    {"id": "execution-outcomes", "name": "Execution outcomes", "description": "Persisted per-run simulation outcomes and suppression counts.", "data_basis": "Local SIMULATION records; no messages were sent."},
]


class ScheduleInput(BaseModel):
    report_id: str
    name: str = Field(min_length=2, max_length=100)
    cadence: Literal["Once", "Daily", "Weekly", "Monthly"]
    export_format: Literal["CSV", "JSON"] = "CSV"
    delivery: Literal["Download only"] = "Download only"


def _report_rows(report_id: str):
    campaigns = store.get_campaigns()
    if report_id == "campaign-performance":
        return [{"campaign_id": c.id, "name": c.name, "status": c.status.value,
                 "objective": c.objective, "channel": c.channel, "audience": c.audience,
                 "reached_observed": c.reached, "conversions_observed": c.conversions,
                 "conversion_rate_observed_percent": round(c.conversions / c.reached * 100, 2) if c.reached else 0,
                 "observed_revenue_pkr": c.revenue, "budget_pkr": c.budget,
                 "observed_revenue_to_budget_percent": round(c.revenue / c.budget * 100, 2) if c.budget else 0,
                 "start_date": c.start_date.isoformat() if c.start_date else None} for c in campaigns]
    if report_id == "channel-performance":
        channels = sorted({c.channel for c in campaigns})
        return [{"channel": channel, "campaigns": sum(c.channel == channel for c in campaigns),
                 "reached_observed": sum(c.reached for c in campaigns if c.channel == channel),
                 "conversions_observed": sum(c.conversions for c in campaigns if c.channel == channel),
                 "observed_revenue_pkr": sum(c.revenue for c in campaigns if c.channel == channel)} for channel in channels]
    if report_id == "customer-cohorts":
        cohorts = sorted({c.segment for c in store.get_customers()})
        return [{"segment": segment, "sample_customers": len(members),
                 "average_monthly_value_pkr": round(sum(c.monthly_value for c in members) / len(members), 2) if members else 0,
                 "average_data_usage_gb": round(sum(c.data_usage_gb for c in members) / len(members), 2) if members else 0,
                 "consented_sample_customers": sum(c.consent for c in members),
                 "high_churn_risk_sample_customers": sum(c.churn_risk == "High" for c in members)}
                for segment in cohorts for members in [[c for c in store.get_customers() if c.segment == segment]]]
    if report_id == "execution-outcomes":
        rows = []
        for run in database.list_records("execution_runs"):
            summary = run.get("summary", {})
            rows.append({"run_id": run["id"], "campaign_id": run.get("campaign_id"),
                         "campaign_name": run.get("campaign_name"), "mode": run.get("mode", "SIMULATION"),
                         "run_status": run.get("status"), "created_at": run.get("created_at"),
                         "targeted": summary.get("targeted", 0), "simulated_delivered": summary.get("simulated_delivered", 0),
                         "failed": summary.get("failed", 0), "dead_letter": summary.get("dead_letter", 0),
                         "consent_excluded": summary.get("consent_excluded", 0), "rule_excluded": summary.get("rule_excluded", 0)})
        return rows
    raise HTTPException(404, "Report definition not found")


@router.get("/definitions")
def list_definitions():
    return DEFINITIONS


@router.get("/{report_id}/data")
def get_report_data(report_id: str):
    rows = _report_rows(report_id)
    definition = next(item for item in DEFINITIONS if item["id"] == report_id)
    return {"report_id": report_id, "name": definition["name"], "data_basis": definition["data_basis"],
            "generated_at": datetime.now(timezone.utc).isoformat(), "row_count": len(rows), "rows": rows}


def _schedules():
    return [row for row in database.list_records("module_actions") if row.get("module") == "reports" and row.get("action") == "report_schedule"]


@router.get("/schedules")
def list_schedules():
    return sorted(_schedules(), key=lambda row: row.get("created_at", ""), reverse=True)


@router.post("/schedules", status_code=201)
def create_schedule(payload: ScheduleInput, current: dict = Depends(require_user)):
    if payload.report_id not in {item["id"] for item in DEFINITIONS}:
        raise HTTPException(404, "Report definition not found")
    now = datetime.now(timezone.utc).isoformat()
    schedule = {"id": f"rpt-{uuid4().hex[:10]}", "module": "reports", "action": "report_schedule",
                "name": payload.name, "report_id": payload.report_id, "cadence": payload.cadence,
                "export_format": payload.export_format, "owner": current["email"],
                "delivery": payload.delivery, "status": "Metadata only", "created_at": now,
                "updated_at": now, "message": "Schedule metadata saved. No background job or email delivery is configured."}
    database.add_action(schedule)
    record_audit_event(current["email"], "report_schedule_saved", "report", payload.report_id,
                       {"schedule_id": schedule["id"], "cadence": payload.cadence, "format": payload.export_format})
    return schedule


@router.patch("/schedules/{schedule_id}")
def update_schedule(schedule_id: str, active: bool, current: dict = Depends(require_user)):
    schedule = next((row for row in _schedules() if row["id"] == schedule_id), None)
    if schedule is None:
        raise HTTPException(404, "Report schedule not found")
    if schedule.get("owner", "").casefold() != current["email"].casefold() and current.get("role") not in ADMIN_ROLES:
        raise HTTPException(403, "You can only update your own report schedules")
    schedule.update({"status": "Metadata only" if active else "Paused", "updated_at": datetime.now(timezone.utc).isoformat()})
    database.save_record("module_actions", schedule_id, schedule)
    record_audit_event(current["email"], "report_schedule_status_changed", "report", schedule["report_id"],
                       {"schedule_id": schedule_id, "status": schedule["status"]})
    return schedule
