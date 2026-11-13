"""Journey definitions and safe, non-delivery execution previews."""
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .. import database, store
from ..services.audit import record_audit_event

router = APIRouter(prefix="/journeys", tags=["journeys"])


class JourneyNode(BaseModel):
    id: str
    type: Literal["trigger", "message", "wait", "condition", "exit"]
    name: str
    x: float = 0
    y: float = 0
    config: dict[str, Any] = Field(default_factory=dict)


class JourneyEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None


class JourneyDefinition(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = ""
    audience_segment_id: str | None = None
    nodes: list[JourneyNode] = Field(default_factory=list)
    edges: list[JourneyEdge] = Field(default_factory=list)


class JourneyCreate(JourneyDefinition):
    pass


def _all() -> list[dict[str, Any]]:
    return database.list_records("journeys")


def _get(journey_id: str) -> dict[str, Any]:
    item = next((row for row in _all() if row["id"] == journey_id), None)
    if item is None:
        raise HTTPException(404, "Journey not found")
    return item


def _validation(definition: JourneyDefinition) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    ids = [node.id for node in definition.nodes]
    if len(set(ids)) != len(ids):
        issues.append({"code": "duplicate_node", "message": "Node IDs must be unique."})
    if sum(node.type == "trigger" for node in definition.nodes) != 1:
        issues.append({"code": "trigger_count", "message": "A journey needs exactly one entry trigger."})
    if not any(node.type == "exit" for node in definition.nodes):
        issues.append({"code": "missing_exit", "message": "Add an exit node to finish the journey."})
    known = set(ids)
    for edge in definition.edges:
        if edge.source not in known or edge.target not in known:
            issues.append({"code": "dangling_edge", "message": f"Connection {edge.id} points to a missing node."})
    outgoing: dict[str, list[str]] = {node_id: [] for node_id in known}
    for edge in definition.edges:
        if edge.source in known and edge.target in known:
            outgoing[edge.source].append(edge.target)
    triggers = [node.id for node in definition.nodes if node.type == "trigger"]
    if triggers:
        reached, pending = set(), list(triggers)
        while pending:
            current = pending.pop()
            if current in reached: continue
            reached.add(current); pending.extend(outgoing.get(current, []))
        if any(node.type == "exit" and node.id not in reached for node in definition.nodes):
            issues.append({"code": "unreachable_exit", "message": "Connect the trigger path to an exit node."})
    for node in definition.nodes:
        if node.type == "message" and not node.config.get("channel"):
            issues.append({"code": "message_channel", "message": f"Choose a channel for {node.name}."})
        if node.type == "wait" and float(node.config.get("duration", 0) or 0) <= 0:
            issues.append({"code": "wait_duration", "message": f"Set a positive wait duration for {node.name}."})
    if definition.audience_segment_id and not any(s.id == definition.audience_segment_id for s in store.get_segments()):
        issues.append({"code": "segment_missing", "message": "The selected audience segment no longer exists."})
    return issues


@router.get("")
def list_journeys():
    return _all()


@router.post("", status_code=201)
def create_journey(payload: JourneyCreate):
    if any(row["name"].casefold() == payload.name.casefold() for row in _all()):
        raise HTTPException(409, "A journey with this name already exists")
    now = datetime.now(timezone.utc).isoformat()
    row = {"id": f"journey-{uuid4().hex[:10]}", **payload.model_dump(mode="json"),
           "version": 1, "status": "Draft", "created_at": now, "updated_at": now}
    database.save_record("journeys", row["id"], row)
    record_audit_event("local-user", "journey_created", "journey", row["id"], {"name": row["name"], "version": row["version"]})
    return row


@router.get("/{journey_id}")
def get_journey(journey_id: str):
    return _get(journey_id)


@router.put("/{journey_id}")
def update_journey(journey_id: str, payload: JourneyCreate):
    current = _get(journey_id)
    if current.get("status") != "Draft":
        raise HTTPException(409, "Only draft journeys can be edited")
    if any(row["id"] != journey_id and row["name"].casefold() == payload.name.casefold() for row in _all()):
        raise HTTPException(409, "A journey with this name already exists")
    updated = {**current, **payload.model_dump(mode="json"), "version": current.get("version", 1) + 1,
               "updated_at": datetime.now(timezone.utc).isoformat()}
    database.save_record("journeys", journey_id, updated)
    record_audit_event("local-user", "journey_updated", "journey", journey_id, {"name": updated["name"], "version": updated["version"]})
    return updated


@router.delete("/{journey_id}", status_code=204)
def delete_journey(journey_id: str):
    _get(journey_id)
    # SQLite abstraction intentionally exposes upsert/list only; mark as archived.
    row = _get(journey_id); row["status"] = "Archived"; row["updated_at"] = datetime.now(timezone.utc).isoformat()
    database.save_record("journeys", journey_id, row)
    record_audit_event("local-user", "journey_archived", "journey", journey_id, {"name": row["name"]})


@router.post("/{journey_id}/validate")
def validate_journey(journey_id: str):
    row = _get(journey_id)
    definition = JourneyDefinition.model_validate(row)
    issues = _validation(definition)
    return {"valid": not issues, "issues": issues, "journey_id": journey_id, "version": row.get("version", 1)}


@router.post("/{journey_id}/preview")
def preview_journey(journey_id: str):
    row = _get(journey_id); definition = JourneyDefinition.model_validate(row)
    issues = _validation(definition)
    customers = list(store.get_customers())
    if definition.audience_segment_id:
        segment = next((s for s in store.get_segments() if s.id == definition.audience_segment_id), None)
        if segment:
            from ..services.segmentation import segment_members
            customers = segment_members(segment, customers)
    opted_in = [customer for customer in customers if customer.consent]
    excluded = len(customers) - len(opted_in)
    return {"journey_id": journey_id, "version": row.get("version", 1), "valid": not issues, "issues": issues,
            "audience_count": len(customers), "eligible_count": len(opted_in), "excluded_no_consent": excluded,
            "sample_customers": [{"id": c.id, "name": c.name, "masked_number": c.identifier,
                                  "preferred_channel": c.preferred_channel, "segment": c.segment}
                                 for c in opted_in[:10]],
            "steps": [{"node_id": n.id, "type": n.type, "name": n.name, "config": n.config} for n in definition.nodes],
            "delivery": "preview_only", "message": "No messages are sent and no customer records are changed."}
