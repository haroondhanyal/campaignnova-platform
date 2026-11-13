from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from .. import store
from ..schemas import Campaign, CampaignCreate, CampaignPatch, CampaignStatus, CampaignTransition
from ..services.segmentation import segment_members
from .authentication import require_user

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("", response_model=list[Campaign])
def list_campaigns(status: CampaignStatus | None = None, q: str | None = Query(default=None, max_length=120),
                   start_date: date | None = None, end_date: date | None = None):
    result = store.get_campaigns()
    if status:
        result = [c for c in result if c.status == status]
    if q:
        result = [c for c in result if q.lower() in c.name.lower() or q.lower() in c.objective.lower()]
    if start_date:
        result = [c for c in result if c.start_date and c.start_date >= start_date]
    if end_date:
        result = [c for c in result if c.start_date and c.start_date <= end_date]
    return result


@router.post("", response_model=Campaign, status_code=201)
def add_campaign(payload: CampaignCreate, current: dict = Depends(require_user)):
    if payload.status != CampaignStatus.DRAFT:
        raise HTTPException(status_code=422, detail="Campaigns must be created as Draft before review")
    validation = validate_campaign(payload)
    failed = [check["message"] for check in validation["checks"] if check["status"] == "error"]
    if failed:
        raise HTTPException(status_code=422, detail={"message": "Campaign validation failed", "checks": failed})
    return store.create_campaign(payload.model_copy(update={"owner": current["email"]}))


def validate_campaign(payload: CampaignCreate):
    checks = []
    segment = next((s for s in store.get_segments() if s.id == payload.segment_id), None) if payload.segment_id else None
    if payload.segment_id and segment is None:
        checks.append({"key": "audience", "status": "error", "message": "Selected audience segment was not found"})
        eligible = []
    else:
        audience = segment_members(segment, store.get_customers()) if segment else list(store.get_customers())
        eligible = [c for c in audience if c.consent]
        checks.append({"key": "audience", "status": "passed", "message": f"{len(audience)} synthetic sample customers in audience"})
    checks.append({"key": "consent", "status": "passed" if eligible else "warning",
                   "message": f"{len(eligible)} sample customers are opted in" if eligible else "No opted-in customers in the local sample"})
    if payload.offer_id:
        offer = next((o for o in store.get_offers() if o.id == payload.offer_id), None)
        if offer is None:
            checks.append({"key": "offer", "status": "error", "message": "Selected offer was not found"})
        elif offer.status != "Active":
            checks.append({"key": "offer", "status": "error", "message": "Only an active offer can be attached to a campaign"})
        else:
            checks.append({"key": "offer", "status": "passed", "message": f"Offer {offer.name} is active"})
    duplicate = next((c for c in store.get_campaigns() if c.name.casefold() == payload.name.casefold()
                      and c.start_date == payload.start_date and c.status != CampaignStatus.CANCELLED), None)
    checks.append({"key": "duplicate", "status": "error" if duplicate else "passed",
                   "message": "A campaign with this name and start date already exists" if duplicate else "No duplicate campaign found"})
    checks.append({"key": "budget", "status": "warning" if payload.budget == 0 else "passed",
                   "message": "Budget is zero; confirm this is intentional" if payload.budget == 0 else f"Budget set to PKR {payload.budget:,.0f}"})
    return {"can_create": not any(check["status"] == "error" for check in checks), "checks": checks,
            "estimate_basis": "synthetic_sample"}


@router.post("/validate")
def validate_campaign_request(payload: CampaignCreate):
    return validate_campaign(payload)


@router.get("/{campaign_id}", response_model=Campaign)
def get_campaign(campaign_id: str):
    for campaign in store.get_campaigns():
        if campaign.id == campaign_id:
            return campaign
    raise HTTPException(status_code=404, detail="Campaign not found")


@router.patch("/{campaign_id}", response_model=Campaign)
def update_campaign(campaign_id: str, payload: CampaignPatch):
    current = next((c for c in store.get_campaigns() if c.id == campaign_id), None)
    if not current:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if current.status != CampaignStatus.DRAFT:
        raise HTTPException(status_code=409, detail="Only draft campaigns can be edited")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    updated = Campaign.model_validate({**current.model_dump(), **changes})
    if updated.start_date and updated.end_date and updated.end_date < updated.start_date:
        raise HTTPException(status_code=422, detail="Campaign end date must be on or after its start date")
    if updated.segment_id and not any(s.id == updated.segment_id for s in store.get_segments()):
        raise HTTPException(status_code=422, detail="Selected segment was not found")
    if updated.offer_id and not any(o.id == updated.offer_id for o in store.get_offers()):
        raise HTTPException(status_code=422, detail="Selected offer was not found")
    return store.save_campaign(updated)


TRANSITIONS = {
    CampaignStatus.DRAFT: set(),
    CampaignStatus.PENDING: set(),
    CampaignStatus.APPROVED: {CampaignStatus.SCHEDULED},
    CampaignStatus.SCHEDULED: set(),
    CampaignStatus.RUNNING: set(),
    CampaignStatus.PAUSED: set(),
    CampaignStatus.FAILED: set(),
    CampaignStatus.COMPLETED: set(),
    CampaignStatus.CANCELLED: set(),
}


@router.post("/{campaign_id}/status", response_model=Campaign)
def transition_campaign(campaign_id: str, payload: CampaignTransition, current_user: dict = Depends(require_user)):
    current = next((c for c in store.get_campaigns() if c.id == campaign_id), None)
    if not current:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if payload.status not in TRANSITIONS[current.status]:
        raise HTTPException(status_code=409, detail=f"Invalid campaign transition: {current.status.value} → {payload.status.value}")
    if payload.status == CampaignStatus.SCHEDULED and current.start_date is None:
        raise HTTPException(status_code=422, detail="Add a start date before scheduling this campaign")
    history = [*current.status_history, {"status": payload.status.value, "actor": current_user["email"],
                                         "reason": payload.reason, "at": datetime.now(timezone.utc).isoformat()}]
    return store.save_campaign(current.model_copy(update={"status": payload.status, "status_history": history}))
