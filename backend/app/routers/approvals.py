from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from .. import database, store
from ..schemas import CampaignStatus
from ..services.audit import record_audit_event
from .authentication import require_user

router = APIRouter(prefix="/approvals", tags=["approvals"])
APPROVER_ROLES = {"Approver", "Department Manager", "CVM Manager", "Admin", "Organization Admin", "Super Admin"}


class ApprovalSubmission(BaseModel):
    resource_type: Literal["campaign", "offer", "scenario"]
    resource_id: str
    summary: str = Field(default="Review requested", max_length=500)


class ApprovalDecision(BaseModel):
    decision: Literal["Approved", "Rejected"]
    reason: str = Field(default="", max_length=500)


def _all() -> list[dict]:
    return database.list_records("approvals")


def _pending_for(resource_type: str, resource_id: str):
    return next((row for row in _all() if row["resource_type"] == resource_type and row["resource_id"] == resource_id and row["status"] == "Pending"), None)


def _new_request(resource_type: str, resource_id: str, requested_by: str, requester_role: str, summary: str):
    if _pending_for(resource_type, resource_id):
        raise HTTPException(status_code=409, detail="This item already has a pending approval request")
    request = {"id": f"apr-{uuid4().hex[:10]}", "resource_type": resource_type, "resource_id": resource_id,
               "requested_by": requested_by, "requester_role": requester_role, "summary": summary,
               "status": "Pending", "created_at": datetime.now(timezone.utc).isoformat(),
               "decision_by": None, "decision_role": None, "decision_reason": None, "decided_at": None}
    database.save_record("approvals", request["id"], request)
    record_audit_event(requested_by, "approval_requested", resource_type, resource_id, {"approval_id": request["id"], "summary": summary})
    return request


def bootstrap_approval_queue() -> None:
    """Create review requests for development seed records that predate the queue."""
    for campaign in store.get_campaigns():
        if campaign.status == CampaignStatus.PENDING and not _pending_for("campaign", campaign.id):
            _new_request("campaign", campaign.id, campaign.owner, "Campaign Manager", "Seed campaign awaiting review")
    for offer in store.get_offers():
        if offer.status == "Pending Approval" and not _pending_for("offer", offer.id):
            _new_request("offer", offer.id, "Campaign Admin", "Campaign Manager", "Seed offer awaiting review")


@router.get("")
def list_approvals(status: str | None = None, resource_type: str | None = None):
    rows = sorted(_all(), key=lambda row: row["created_at"], reverse=True)
    if status:
        rows = [row for row in rows if row["status"] == status]
    if resource_type:
        rows = [row for row in rows if row["resource_type"] == resource_type]
    return rows


@router.post("", status_code=201)
def submit_approval(payload: ApprovalSubmission, current: dict = Depends(require_user)):
    role = current.get("role", "")
    submit_role = role if role in {"Campaign Manager", "CVM Manager", "Approver", "Organization Admin", "Super Admin"} else "Campaign Manager"
    if payload.resource_type == "campaign":
        resource = next((item for item in store.get_campaigns() if item.id == payload.resource_id), None)
        if resource is None:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if resource.status != CampaignStatus.DRAFT:
            raise HTTPException(status_code=409, detail="Only draft campaigns can be submitted for approval")
        history = [*resource.status_history, {"status": CampaignStatus.PENDING.value, "actor": current["email"],
                                             "reason": payload.summary, "at": datetime.now(timezone.utc).isoformat()}]
        store.save_campaign(resource.model_copy(update={"status": CampaignStatus.PENDING, "status_history": history}))
    elif payload.resource_type == "offer":
        resource = next((item for item in store.get_offers() if item.id == payload.resource_id), None)
        if resource is None:
            raise HTTPException(status_code=404, detail="Offer not found")
        if resource.status != "Draft":
            raise HTTPException(status_code=409, detail="Only draft offers can be submitted for approval")
        history = [*resource.status_history, {"status": "Pending Approval", "actor": current["email"],
                                             "reason": payload.summary, "at": datetime.now(timezone.utc).isoformat()}]
        store.save_offer(resource.model_copy(update={"status": "Pending Approval", "status_history": history,
                                                     "version": resource.version + 1}))
    else:
        resource = next((item for item in store.get_scenarios() if item.id == payload.resource_id), None)
        if resource is None:
            raise HTTPException(status_code=404, detail="Scenario not found")
        if resource.status != "Draft":
            raise HTTPException(status_code=409, detail="Only draft scenarios can be submitted for approval")
    return _new_request(payload.resource_type, payload.resource_id, current["email"], submit_role, payload.summary)


@router.post("/{approval_id}/decision")
def decide_approval(approval_id: str, payload: ApprovalDecision, current: dict = Depends(require_user)):
    actor_role = current.get("role", "")
    actor = current["email"]
    if actor_role not in APPROVER_ROLES:
        raise HTTPException(status_code=403, detail="Your account role cannot decide approval requests")
    request = next((row for row in _all() if row["id"] == approval_id), None)
    if request is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if request["status"] != "Pending":
        raise HTTPException(status_code=409, detail="Approval request has already been decided")
    if request["requested_by"].casefold() == actor.casefold():
        raise HTTPException(status_code=403, detail="The requester cannot approve their own request")
    approved = payload.decision == "Approved"
    now = datetime.now(timezone.utc).isoformat()
    resource_type, resource_id = request["resource_type"], request["resource_id"]
    if resource_type == "campaign":
        resource = next((item for item in store.get_campaigns() if item.id == resource_id), None)
        if resource is None or resource.status != CampaignStatus.PENDING:
            raise HTTPException(status_code=409, detail="Campaign is no longer awaiting approval")
        target = CampaignStatus.APPROVED if approved else CampaignStatus.DRAFT
        history = [*resource.status_history, {"status": target.value, "actor": actor, "reason": payload.reason, "at": now}]
        store.save_campaign(resource.model_copy(update={"status": target, "status_history": history}))
    elif resource_type == "offer":
        resource = next((item for item in store.get_offers() if item.id == resource_id), None)
        if resource is None or resource.status != "Pending Approval":
            raise HTTPException(status_code=409, detail="Offer is no longer awaiting approval")
        target = "Active" if approved else "Draft"
        history = [*resource.status_history, {"status": target, "actor": actor, "reason": payload.reason, "at": now}]
        store.save_offer(resource.model_copy(update={"status": target, "status_history": history, "version": resource.version + 1}))
    else:
        resource = next((item for item in store.get_scenarios() if item.id == resource_id), None)
        if resource is None or resource.status != "Draft":
            raise HTTPException(status_code=409, detail="Scenario is no longer awaiting approval")
        if approved:
            store.save_scenario(resource.model_copy(update={"status": "Ready", "version": resource.version + 1,
                                                             "updated_at": datetime.now(timezone.utc)}))
    request.update({"status": payload.decision, "decision_by": actor, "decision_role": actor_role,
                    "decision_reason": payload.reason, "decided_at": now})
    database.save_record("approvals", request["id"], request)
    record_audit_event(actor, "approval_decided", resource_type, resource_id,
                       {"approval_id": approval_id, "decision": payload.decision, "reason": payload.reason})
    return request
