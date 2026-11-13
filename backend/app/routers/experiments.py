"""Experiment plans and consent-filtered allocation previews; no outcome claims."""
from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from .. import database, store
from ..services.segmentation import segment_members
from ..services.audit import record_audit_event

router = APIRouter(prefix="/experiments", tags=["experiments"])


class Variant(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    allocation_percent: int = Field(ge=1, le=99)


class ExperimentInput(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    hypothesis: str = Field(min_length=10, max_length=1000)
    primary_metric: Literal["conversion", "revenue", "recharge", "usage", "retention"]
    audience_segment_id: str | None = None
    variants: list[Variant] = Field(min_length=2, max_length=4)
    notes: str = Field(default="", max_length=1000)

    @field_validator("variants")
    @classmethod
    def valid_allocation(cls, variants):
        names = [variant.name.casefold() for variant in variants]
        if len(names) != len(set(names)):
            raise ValueError("Variant names must be unique")
        if sum(variant.allocation_percent for variant in variants) != 100:
            raise ValueError("Variant allocation percentages must add up to 100")
        return variants


def _definitions():
    return [item for item in database.list_records("module_actions")
            if item.get("module") == "experiments" and item.get("action") == "definition"]


def _get(experiment_id: str):
    row = next((item for item in _definitions() if item["id"] == experiment_id), None)
    if row is None:
        raise HTTPException(404, "Experiment not found")
    return row


def _save(row):
    database.add_action(row)
    return row


def _validate_segment(segment_id: str | None):
    if segment_id and not any(segment.id == segment_id for segment in store.get_segments()):
        raise HTTPException(422, "Selected audience segment was not found")


@router.get("")
def list_experiments():
    return sorted(_definitions(), key=lambda row: row.get("created_at", ""), reverse=True)


@router.post("", status_code=201)
def create_experiment(payload: ExperimentInput):
    if any(row["status"] != "Archived" and row["name"].casefold() == payload.name.casefold() for row in _definitions()):
        raise HTTPException(409, "An experiment with this name already exists")
    _validate_segment(payload.audience_segment_id)
    now = datetime.now(timezone.utc).isoformat()
    row = {"id": f"exp-{uuid4().hex[:10]}", "module": "experiments", "action": "definition",
           **payload.model_dump(mode="json"), "status": "Draft", "created_at": now,
           "updated_at": now, "outcome_status": "Unmeasured"}
    saved = _save(row)
    record_audit_event("local-user", "experiment_plan_created", "experiment", row["id"], {"name": row["name"], "metric": row["primary_metric"]})
    return saved


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str):
    return _get(experiment_id)


@router.put("/{experiment_id}")
def update_experiment(experiment_id: str, payload: ExperimentInput):
    current = _get(experiment_id)
    if current.get("status") != "Draft":
        raise HTTPException(409, "Only draft experiment plans can be edited")
    if any(row["id"] != experiment_id and row["status"] != "Archived" and row["name"].casefold() == payload.name.casefold() for row in _definitions()):
        raise HTTPException(409, "An experiment with this name already exists")
    _validate_segment(payload.audience_segment_id)
    updated = {**current, **payload.model_dump(mode="json"), "updated_at": datetime.now(timezone.utc).isoformat()}
    saved = _save(updated)
    record_audit_event("local-user", "experiment_plan_updated", "experiment", experiment_id, {"name": updated["name"]})
    return saved


@router.delete("/{experiment_id}", status_code=204)
def archive_experiment(experiment_id: str):
    row = _get(experiment_id)
    row.update({"status": "Archived", "updated_at": datetime.now(timezone.utc).isoformat()})
    _save(row)
    record_audit_event("local-user", "experiment_plan_archived", "experiment", experiment_id, {"name": row["name"]})


@router.post("/{experiment_id}/archive")
def archive_experiment_action(experiment_id: str):
    row = _get(experiment_id)
    row.update({"status": "Archived", "updated_at": datetime.now(timezone.utc).isoformat()})
    saved = _save(row)
    record_audit_event("local-user", "experiment_plan_archived", "experiment", experiment_id, {"name": row["name"]})
    return saved


@router.post("/{experiment_id}/preview")
def preview_allocation(experiment_id: str):
    experiment = _get(experiment_id)
    audience = list(store.get_customers())
    segment_id = experiment.get("audience_segment_id")
    if segment_id:
        segment = next((item for item in store.get_segments() if item.id == segment_id), None)
        if segment is None:
            raise HTTPException(409, "Saved segment no longer exists")
        audience = segment_members(segment, audience)
    eligible = [customer for customer in audience if customer.consent and customer.subscription_status == "Active"]
    excluded = len(audience) - len(eligible)
    counts = [0] * len(experiment["variants"])
    # Stable hashing gives a repeatable count preview only; individual assignments are neither stored nor activated.
    for customer in eligible:
        value = int.from_bytes(sha256(f"{experiment['id']}:{customer.id}".encode()).digest()[:8], "big") % 10000 / 100
        cumulative = 0
        for index, variant in enumerate(experiment["variants"]):
            cumulative += variant["allocation_percent"]
            if value < cumulative:
                counts[index] += 1
                break
    return {"experiment_id": experiment_id, "preview_only": True, "assignment_created": False,
            "audience_sample": len(audience), "eligible_consented_active_sample": len(eligible),
            "excluded_without_consent_or_inactive": excluded,
            "allocations": [{"variant": variant["name"], "allocation_percent": variant["allocation_percent"],
                             "preview_sample_count": counts[index]}
                            for index, variant in enumerate(experiment["variants"])],
            "primary_metric": experiment["primary_metric"], "outcome_status": "Unmeasured",
            "message": "Preview counts only. No customers were assigned, contacted, or measured."}
