from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from .. import store
from ..schemas import CustomerConsentUpdate

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("")
def list_customers(q: str | None = None, segment: str | None = None):
    result = store.get_customers()
    if q:
        needle = q.lower()
        result = [c for c in result if needle in c.name.lower() or needle in c.id.lower() or needle in c.identifier.lower()]
    if segment:
        result = [c for c in result if c.segment.lower() == segment.lower()]
    return {"items": [c.model_dump(mode="json") for c in result], "total": len(result), "data_mode": "synthetic-sqlite"}


@router.get("/{customer_id}")
def get_customer(customer_id: str):
    for customer in store.get_customers():
        if customer.id == customer_id:
            profile = customer.model_dump(mode="json")
            profile["campaign_timeline"] = [
                {"campaign_id": campaign.id, "campaign": campaign.name, "status": campaign.status.value,
                 "channel": campaign.channel, "date": campaign.start_date.isoformat() if campaign.start_date else None}
                for campaign in store.get_campaigns()
                if campaign.id in customer.campaign_participation or campaign.audience.lower() == customer.segment.lower() or campaign.segment_id == customer.segment
            ]
            return profile
    raise HTTPException(status_code=404, detail="Customer not found")


@router.patch("/{customer_id}/consent")
def update_customer_consent(customer_id: str, payload: CustomerConsentUpdate):
    customer = next((c for c in store.get_customers() if c.id == customer_id), None)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    changed_at = datetime.now(timezone.utc)
    history = [*customer.consent_history, {"consent": payload.consent, "reason": payload.reason, "at": changed_at.isoformat()}]
    updated = store.save_customer(customer.model_copy(update={"consent": payload.consent, "consent_history": history, "updated_at": changed_at}))
    return {"customer_id": updated.id, "consent": updated.consent, "reason": payload.reason,
            "updated_at": updated.updated_at.isoformat()}
