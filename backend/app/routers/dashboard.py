from collections import Counter
from fastapi import APIRouter
from .. import store
from ..schemas import CampaignStatus

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def dashboard():
    records = store.get_campaigns()
    running = [c for c in records if c.status == CampaignStatus.RUNNING]
    reached = sum(c.reached for c in records)
    conversions = sum(c.conversions for c in records)
    revenue = sum(c.revenue for c in records)
    budget = sum(c.budget for c in records)
    return {
        "data_mode": "synthetic-sqlite",
        "metrics": {
            "total_campaigns": len(records),
            "active_campaigns": len(running),
            "scheduled_campaigns": sum(c.status == CampaignStatus.SCHEDULED for c in records),
            "completed_campaigns": sum(c.status == CampaignStatus.COMPLETED for c in records),
            "customers_reached": reached,
            "conversion_rate": round(conversions / reached * 100, 1) if reached else 0,
            "observed_revenue_pkr": revenue,
            "roi_percent": round(revenue / budget * 100, 1) if budget else 0,
        },
        "status_breakdown": dict(Counter(c.status.value for c in records)),
        "campaigns": [c.model_dump(mode="json") for c in records[:5]],
        "channel_performance": [
            {"channel": channel, "reached": sum(c.reached for c in records if c.channel == channel),
             "conversions": sum(c.conversions for c in records if c.channel == channel)}
            for channel in sorted({c.channel for c in records})
        ],
        "insights": [],
    }
