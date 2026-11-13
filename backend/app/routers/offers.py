from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from .. import store
from ..schemas import Offer, OfferCreate, OfferPatch, OfferStatusUpdate
from .authentication import require_user

router = APIRouter(prefix="/offers", tags=["offers"])


@router.get("", response_model=list[Offer])
def list_offers(status: str | None = None, q: str | None = None):
    result = store.get_offers()
    if status:
        result = [offer for offer in result if offer.status == status]
    if q:
        result = [offer for offer in result if q.casefold() in offer.name.casefold() or q.casefold() in offer.product.casefold()]
    return result


@router.post("", response_model=Offer, status_code=201)
def create_offer(payload: OfferCreate, current: dict = Depends(require_user)):
    if payload.status != "Draft":
        raise HTTPException(status_code=422, detail="New offers must start in Draft status")
    return store.create_offer(payload, current["email"])


@router.get("/{offer_id}", response_model=Offer)
def get_offer(offer_id: str):
    offer = next((item for item in store.get_offers() if item.id == offer_id), None)
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.patch("/{offer_id}", response_model=Offer)
def update_offer(offer_id: str, payload: OfferPatch, current_user: dict = Depends(require_user)):
    current = next((item for item in store.get_offers() if item.id == offer_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    if current.status != "Draft":
        raise HTTPException(status_code=409, detail="Only draft offers can be edited")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    updated = Offer.model_validate({**current.model_dump(), **changes})
    if updated.start_date and updated.end_date and updated.end_date < updated.start_date:
        raise HTTPException(status_code=422, detail="Offer end date must be on or after its start date")
    version = current.version + 1
    version_history = [*current.version_history, {"version": version, "actor": current_user["email"],
                                                   "changed_fields": sorted(changes), "snapshot": updated.model_dump(mode="json"),
                                                   "at": datetime.now(timezone.utc).isoformat()}]
    return store.save_offer(updated.model_copy(update={"version": version, "version_history": version_history, "updated_at": date.today()}))


OFFER_TRANSITIONS = {
    "Draft": set(),
    "Pending Approval": set(),
    "Active": {"Expired"},
    "Expired": set(),
}


@router.post("/{offer_id}/status", response_model=Offer)
def transition_offer(offer_id: str, payload: OfferStatusUpdate, current_user: dict = Depends(require_user)):
    current = next((item for item in store.get_offers() if item.id == offer_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    if payload.status not in OFFER_TRANSITIONS[current.status]:
        raise HTTPException(status_code=409, detail=f"Invalid offer transition: {current.status} → {payload.status}")
    history = [*current.status_history, {"status": payload.status, "actor": current_user["email"],
                                         "reason": payload.reason, "at": datetime.now(timezone.utc).isoformat()}]
    version = current.version + 1
    version_history = [*current.version_history, {"version": version, "actor": current_user["email"],
                                                   "changed_fields": ["status"], "status": payload.status,
                                                   "reason": payload.reason, "at": datetime.now(timezone.utc).isoformat()}]
    updated = current.model_copy(update={"status": payload.status, "status_history": history,
                                        "updated_at": date.today(), "version": version, "version_history": version_history})
    return store.save_offer(updated)
