from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from .. import store

router = APIRouter(prefix="/modules", tags=["module workspaces"])

MODULES = {
    "campaign-studio": ("Campaign Studio", "Campaign CRUD and draft creation are available."),
    "scenario-studio": ("Scenario Studio", "Reusable scenarios target saved segments, offers, consent and channel preferences."),
    "campaign-calendar": ("Campaign Calendar", "Campaign dates are read from the campaign API."),
    "customer-360": ("Customer 360", "Synthetic customer profiles are available with masked identifiers."),
    "audience-segments": ("Audience & Segments", "Saved synthetic segments are available."),
    "ai-segment-builder": ("AI Segment Builder", "Rule-assisted audience estimation over the local synthetic customer sample; no ML model is used."),
    "offer-management": ("Offer Management", "The synthetic offer catalog is available."),
    "journey-orchestration": ("Journey Orchestration", "Build and validate customer journeys with consent-filtered audience previews."),
    "workflow-automation": ("Workflow Automation", "Overview of saved journeys, active business rules, and local execution simulations."),
    "campaign-execution": ("Campaign Execution", "Observe local campaign simulations, retries and customer-level outcomes. No messages are sent."),
    "channel-management": ("Channel Management", "Review provider and delivery requirements; no external channels are connected."),
    "nova-ai": ("Nova AI Assistant", "Optional server-side Gemini assistance with a local rule/template fallback over synthetic workspace data."),
    "predictive-intelligence": ("Predictive Intelligence", "Explainable descriptive and rule-based cues; no evaluated predictive model is available."),
    "ab-testing": ("A/B Testing", "Plan experiment hypotheses and consent-filtered sample allocation previews; outcomes remain unmeasured."),
    "analytics-insights": ("Analytics & Insights", "Observed descriptive aggregates and explicit record review signals."),
    "reports-exports": ("Reports & Exports", "Explore observed synthetic and simulated metrics; download CSV or JSON reports."),
    "integrations": ("Data Integration Hub", "External integrations are not configured."),
    "business-rules": ("Business Rules Engine", "Configure eligibility, frequency caps and quiet-hour suppression."),
    "approvals": ("Approvals & Governance", "Review campaign, offer and scenario requests with an auditable decision trail."),
    "user-roles": ("User & Role Management", "Maintain a local role catalog and directory plan. API authorization is not enabled."),
    "audit-logs": ("Audit Logs", "Development action requests are recorded in SQLite."),
    "settings": ("System Configuration", "Save workspace preferences and inspect development connection status."),
    "feature-access": ("Feature Access", "Request optional modules, review approvals, and manage department-level access."),
}
PLANNED_MODULES = set()


class ModuleAction(BaseModel):
    action: str = Field(min_length=2, max_length=80)
    label: str = Field(min_length=2, max_length=160)


@router.get("")
def list_modules():
    return [{"key": key, "title": title, "description": description} for key, (title, description) in MODULES.items()]


@router.get("/{module_key}")
def get_module(module_key: str):
    if module_key not in MODULES:
        raise HTTPException(status_code=404, detail="Module not found")
    title, description = MODULES[module_key]
    if module_key in ("campaign-studio", "campaign-calendar"):
        items = [c.model_dump(mode="json") for c in store.get_campaigns()]
    elif module_key == "scenario-studio":
        items = [s.model_dump(mode="json") for s in store.get_scenarios()]
    elif module_key in ("customer-360",):
        items = [c.model_dump() for c in store.get_customers()]
    elif module_key in ("audience-segments", "ai-segment-builder"):
        items = [s.model_dump(mode="json") for s in store.get_segments()]
    elif module_key == "offer-management":
        items = [o.model_dump() for o in store.get_offers()]
    elif module_key in {"journey-orchestration", "campaign-execution", "business-rules", "approvals", "integrations"}:
        table = {"journey-orchestration": "journeys", "campaign-execution": "execution_runs",
                 "business-rules": "business_rules", "approvals": "approvals", "integrations": "integrations"}[module_key]
        items = store.database.list_records(table)
    elif module_key == "audit-logs":
        items = list(reversed(store.database.list_records("audit_events"))) + list(reversed(store.get_module_actions()))
    else:
        items = []
    return {"key": module_key, "title": title, "description": description, "items": items,
            "capability": "planned" if module_key in PLANNED_MODULES else "available",
            "data_mode": "synthetic-sqlite"}


@router.post("/{module_key}/actions", status_code=202)
def create_module_action(module_key: str, payload: ModuleAction):
    if module_key not in MODULES:
        raise HTTPException(status_code=404, detail="Module not found")
    record = {"id": f"act-{uuid4().hex[:12]}", "module": module_key,
              "action": payload.action, "label": payload.label, "status": "recorded",
              "created_at": datetime.now(timezone.utc).isoformat()}
    store.database.add_action(record)
    return {**record, "message": "Action request recorded in the local workspace log."}
