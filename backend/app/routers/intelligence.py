"""Explainable analytics over the local synthetic sample and observed records."""
from collections import defaultdict
from statistics import median
from typing import Literal

from fastapi import APIRouter

from .. import database, store

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def _campaign_metrics(campaigns):
    reached = sum(c.reached for c in campaigns)
    conversions = sum(c.conversions for c in campaigns)
    revenue = sum(c.revenue for c in campaigns)
    return {"campaign_count": len(campaigns), "reached": reached, "conversions": conversions,
            "conversion_rate_percent": round(conversions / reached * 100, 2) if reached else None,
            "observed_revenue_pkr": revenue}


@router.get("/overview")
def intelligence_overview():
    customers, campaigns = store.get_customers(), store.get_campaigns()
    reached = sum(c.reached for c in campaigns)
    conversions = sum(c.conversions for c in campaigns)
    runs = database.list_records("execution_runs")
    simulated_delivered = sum(run.get("summary", {}).get("simulated_delivered", 0) for run in runs)
    simulated_failed = sum(run.get("summary", {}).get("failed", 0) for run in runs)
    signals = []
    for campaign in campaigns:
        if campaign.status.value == "Running" and campaign.reached == 0:
            signals.append({"type": "no_observed_reach", "severity": "review", "entity": campaign.name,
                            "message": "Campaign is marked running but has no observed reach recorded."})
        if campaign.budget > 0 and campaign.revenue == 0 and campaign.status.value in {"Running", "Completed"}:
            signals.append({"type": "no_observed_revenue", "severity": "review", "entity": campaign.name,
                            "message": "Budget is set while observed revenue is zero; confirm the measurement window and data."})
    if simulated_failed:
        signals.append({"type": "simulation_failures", "severity": "info", "entity": "Local execution simulations",
                        "message": f"{simulated_failed} simulated customer outcomes are marked failed. These are local adapter results, not provider delivery events."})
    return {
        "data_mode": "synthetic_sqlite_sample",
        "analytics_method": "descriptive_only",
        "sample": {"customers": len(customers), "campaign_records": len(campaigns), "execution_simulations": len(runs)},
        "observed_campaigns": _campaign_metrics(campaigns),
        "observed_customer_profile": {
            "consented_sample": sum(c.consent for c in customers),
            "average_monthly_value_pkr": round(sum(c.monthly_value for c in customers) / len(customers), 2) if customers else 0,
            "average_data_usage_gb": round(sum(c.data_usage_gb for c in customers) / len(customers), 2) if customers else 0,
            "high_churn_risk_sample": sum(c.churn_risk.casefold() == "high" for c in customers),
        },
        "simulation_only": {"simulated_delivered": simulated_delivered, "simulated_failed": simulated_failed,
                            "provider_delivery_events": 0},
        "signals": signals,
        "limitations": ["Metrics describe the small local synthetic sample and seeded campaign records.",
                        "No significance tests, causal lift, or evaluated predictive model are available."],
    }


@router.get("/cohorts")
def cohort_breakdown(dimension: Literal["segment", "churn_risk", "customer_type", "preferred_channel", "subscription_status"] = "segment"):
    groups = defaultdict(list)
    for customer in store.get_customers():
        groups[str(getattr(customer, dimension, "Unknown"))].append(customer)
    rows = []
    for label, customers in sorted(groups.items()):
        rows.append({"cohort": label, "sample_customers": len(customers),
                     "consented": sum(c.consent for c in customers),
                     "average_monthly_value_pkr": round(sum(c.monthly_value for c in customers) / len(customers), 2),
                     "average_data_usage_gb": round(sum(c.data_usage_gb for c in customers) / len(customers), 2),
                     "high_churn_risk": sum(c.churn_risk.casefold() == "high" for c in customers)})
    return {"dimension": dimension, "basis": "local_synthetic_customer_sample", "sample_total": len(store.get_customers()),
            "cohorts": rows, "interpretation": "Descriptive cohort aggregates only; small sample and no statistical inference."}


@router.get("/campaign-comparison")
def campaign_comparison(dimension: Literal["channel", "objective"] = "channel"):
    groups = defaultdict(list)
    for campaign in store.get_campaigns():
        groups[str(getattr(campaign, dimension, "Unknown"))].append(campaign)
    rows = []
    for label, campaigns in sorted(groups.items()):
        rows.append({"group": label, **_campaign_metrics(campaigns),
                     "average_budget_pkr": round(sum(c.budget for c in campaigns) / len(campaigns), 2)})
    return {"dimension": dimension, "basis": "seeded_campaign_observations", "groups": rows,
            "method": "descriptive_aggregate_no_significance_test",
            "note": "Comparisons are observational and may differ in audience, timing, and budget; they do not estimate causal lift."}


@router.get("/signals")
def observed_signals():
    overview = intelligence_overview()
    campaigns = store.get_campaigns()
    values = [campaign.revenue for campaign in campaigns]
    midpoint = median(values) if values else 0
    signals = list(overview["signals"])
    for campaign in campaigns:
        # This is a transparent review hint using the current sample's median, not a statistical anomaly score.
        if len(values) >= 3 and campaign.revenue > 0 and midpoint > 0 and campaign.revenue >= midpoint * 2:
            signals.append({"type": "revenue_above_sample_median", "severity": "info", "entity": campaign.name,
                            "message": f"Observed revenue is at least twice this sample's median ({midpoint:,.0f} PKR); inspect the underlying campaign records."})
    return {"basis": "explicit_rules_on_observed_records", "statistical_anomaly_detection": False,
            "signals": signals, "note": "Review hints only. Sample size is small; no claim of statistical anomaly or causality."}


@router.get("/offer-fit")
def offer_fit_suggestions(limit: int = 20):
    """Rule-based product-fit cues from existing fields, not a propensity model."""
    suggestions = []
    active_offers = [offer for offer in store.get_offers() if offer.status == "Active"]
    for customer in store.get_customers():
        if not customer.consent or customer.subscription_status != "Active":
            continue
        if customer.churn_risk.casefold() == "high":
            desired = "loyalty" if customer.monthly_value >= 3000 else "discount"
            reasons = ["Existing profile labels churn risk High", f"Monthly value PKR {customer.monthly_value:,.0f}"]
        elif customer.data_usage_gb >= 10:
            desired = "data"
            reasons = [f"Existing profile records {customer.data_usage_gb:g} GB data usage"]
        else:
            desired = "hybrid"
            reasons = [f"Existing plan: {customer.plan}", f"Preferred channel: {customer.preferred_channel}"]
        match = next((offer for offer in active_offers if desired in f"{offer.product} {offer.name}".casefold()), None)
        if match is None and active_offers:
            match = active_offers[0]
        suggestions.append({"customer_id": customer.id, "masked_identifier": customer.identifier,
                            "profile_segment": customer.segment, "existing_churn_label": customer.churn_risk,
                            "suggested_offer": {"id": match.id, "name": match.name, "product": match.product} if match else None,
                            "preferred_channel": customer.preferred_channel, "reasons": reasons,
                            "method": "transparent_rule_based_fit", "probability": None,
                            "message": "Heuristic fit cue only; not an evaluated propensity or next-best-offer model."})
    return {"basis": "consented_active_local_sample", "model_status": "no_evaluated_model",
            "suggestions": suggestions[:max(1, min(limit, 100))],
            "note": "No probability or confidence score is inferred. Suggestions are informational and require human review."}
