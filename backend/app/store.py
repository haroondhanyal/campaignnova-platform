"""Development store initialized from SQLite seed records."""
from datetime import date, datetime, timezone
from uuid import uuid4
from . import database
from .schemas import Campaign, CampaignCreate, Customer, Offer, OfferCreate, Scenario, ScenarioCreate, Segment, SegmentCondition, SegmentCreate, SegmentRuleGroup

campaigns: list[Campaign] = [
    Campaign(id="cmp-2401", name="Prepaid recharge boost", objective="Revenue Growth", channel="SMS", audience="High value prepaid", start_date=date(2026, 11, 15), budget=12000, status="Running", created_at=datetime.now(timezone.utc), reached=48200, conversions=5290, revenue=48600),
    Campaign(id="cmp-2402", name="Win back inactive customers", objective="Win-back", channel="WhatsApp", audience="No recharge in 30 days", start_date=date(2026, 11, 18), budget=8000, status="Scheduled", created_at=datetime.now(timezone.utc), reached=0, conversions=0, revenue=0),
    Campaign(id="cmp-2403", name="4G upgrade journey", objective="Upselling", channel="Push", audience="3G device owners", budget=5000, status="Pending Approval", created_at=datetime.now(timezone.utc), reached=0, conversions=0, revenue=0),
]

customers = [
    Customer(id="cus-1001", name="Ayesha Khan", identifier="0300••••241", segment="High Value Prepaid", plan="Super Data 30GB", monthly_value=4850, churn_risk="Low", consent=True, tenure_days=820, data_usage_gb=24.6, voice_usage_minutes=312, sms_usage=18, preferred_channel="WhatsApp", lifetime_value=93500, recharge_history=[{"date":"2026-11-08","amount":1500},{"date":"2026-10-29","amount":1000}], revenue_history=[{"month":"2026-10","amount":4850},{"month":"2026-09","amount":4620}], engagement_history=[{"date":"2026-11-02","event":"Opened data bundle message"}], campaign_participation=["cmp-2401"]),
    Customer(id="cus-1002", name="Hamza Ali", identifier="0301••••882", segment="At Risk", plan="Hybrid Plus", monthly_value=3200, churn_risk="High", consent=True, customer_type="Hybrid", tenure_days=420, data_usage_gb=4.2, voice_usage_minutes=88, sms_usage=4, preferred_channel="SMS", lifetime_value=44200, recharge_history=[{"date":"2026-11-01","amount":700}], revenue_history=[{"month":"2026-10","amount":3200},{"month":"2026-09","amount":2750}], engagement_history=[{"date":"2026-10-27","event":"Data usage declined"}]),
    Customer(id="cus-1003", name="Sana Ahmed", identifier="0302••••510", segment="New Customers", plan="Weekly Voice", monthly_value=1250, churn_risk="Medium", consent=False, tenure_days=38, data_usage_gb=2.1, voice_usage_minutes=145, sms_usage=32, preferred_channel="Push", lifetime_value=2650, recharge_history=[{"date":"2026-11-10","amount":500}], revenue_history=[{"month":"2026-10","amount":1250}], engagement_history=[{"date":"2026-11-05","event":"Activated weekly package"}]),
]

segments = [
    Segment(id="seg-01", name="High Value Prepaid", description="Prepaid customers with monthly value above PKR 3,000", customer_count=48200, updated_at=date(2026, 11, 12), rules=SegmentRuleGroup(combinator="AND", conditions=[SegmentCondition(field="customer_type", operator="eq", value="Prepaid"), SegmentCondition(field="monthly_value", operator="gt", value=3000)])),
    Segment(id="seg-02", name="At Risk", description="Customers with declining usage and elevated churn signals", customer_count=12640, updated_at=date(2026, 11, 11), rules=SegmentRuleGroup(combinator="AND", conditions=[SegmentCondition(field="churn_risk", operator="eq", value="High")])),
    Segment(id="seg-03", name="New Customers", description="Customers activated in the last 60 days", customer_count=34800, updated_at=date(2026, 11, 10), rules=SegmentRuleGroup(combinator="AND", conditions=[SegmentCondition(field="tenure_days", operator="lt", value=60)])),
]

offers = [
    Offer(id="off-01", name="Power Data 10GB", product="Data bundle", price=450, validity_days=7, status="Active"),
    Offer(id="off-02", name="Hybrid Plus Upgrade", product="Hybrid bundle", price=1200, validity_days=30, status="Active"),
    Offer(id="off-03", name="Loyalty 2X Points", product="Loyalty reward", price=0, validity_days=14, status="Pending Approval"),
]

scenarios = [
    Scenario(id="scn-1001", name="Prepaid recharge win-back", description="Re-engage opted-in prepaid customers with a recharge offer.", objective="Retention", segment_id="seg-02", offer_id="off-01", channel="WhatsApp", message_template="Hi {{name}}, your data bundle is ready. Review offer {{offer_name}} in the app.", status="Draft", version=1, created_at=datetime.now(timezone.utc)),
    Scenario(id="scn-1002", name="High-value data booster", description="Offer a relevant data bundle to high-value customers.", objective="Usage Stimulation", segment_id="seg-01", offer_id="off-01", channel="SMS", message_template="Hi {{name}}, explore this week's data offer in the app.", status="Draft", version=1, created_at=datetime.now(timezone.utc)),
    Scenario(id="scn-1003", name="New customer onboarding", description="Introduce service tips to recently activated customers.", objective="Product Adoption", segment_id="seg-03", channel="Push", message_template="Welcome {{name}}. See tips for getting started in the app.", status="Draft", version=1, created_at=datetime.now(timezone.utc)),
]

module_actions: list[dict] = []


def initialize() -> None:
    """Create the local database, seed it once, then load persistent records."""
    global campaigns, customers, segments, offers, scenarios, module_actions
    database.initialize({"campaigns": campaigns, "customers": customers, "segments": segments, "offers": offers,
                         "scenarios": scenarios, "scenario_runs": [], "journeys": [], "business_rules": [],
                         "execution_runs": [], "approvals": [], "audit_events": [], "integrations": [],
                         "campaign_audiences": [],
                         "oauth_identities": [],
                         "workspace_users": [], "workspace_settings": [],
                         "auth_sessions": [], "password_resets": [], "feature_requests": []})
    database.save_record("workspace_tenants", "campaignnova-demo", {
        "id": "campaignnova-demo", "slug": "campaignnova-demo", "name": "CampaignNova Demo Workspace",
        "created_at": datetime.now(timezone.utc).isoformat(), "tenant_id": "__global__",
    })
    campaigns = [Campaign.model_validate(row) for row in database.list_records("campaigns")]
    customers = [Customer.model_validate(row) for row in database.list_records("customers")]
    segments = [Segment.model_validate(row) for row in database.list_records("segments")]
    offers = [Offer.model_validate(row) for row in database.list_records("offers")]
    scenarios = [Scenario.model_validate(row) for row in database.list_records("scenarios")]
    module_actions = database.list_records("module_actions")


def get_campaigns() -> list[Campaign]:
    return [Campaign.model_validate(row) for row in database.list_records("campaigns")]


def get_customers() -> list[Customer]:
    return [Customer.model_validate(row) for row in database.list_records("customers")]


def get_segments() -> list[Segment]:
    return [Segment.model_validate(row) for row in database.list_records("segments")]


def get_offers() -> list[Offer]:
    return [Offer.model_validate(row) for row in database.list_records("offers")]


def get_scenarios() -> list[Scenario]:
    return [Scenario.model_validate(row) for row in database.list_records("scenarios")]


def get_module_actions() -> list[dict]:
    return database.list_records("module_actions")

def create_campaign(payload: CampaignCreate) -> Campaign:
    created_at = datetime.now(timezone.utc)
    campaign = Campaign(id=f"cmp-{uuid4().hex[:8]}", created_at=created_at,
                        status_history=[{"status": payload.status.value, "actor": payload.owner, "reason": "Campaign created", "at": created_at.isoformat()}],
                        **payload.model_dump())
    campaigns.insert(0, campaign)
    database.save_record("campaigns", campaign.id, campaign.model_dump(mode="json"))
    return campaign


def save_campaign(campaign: Campaign) -> Campaign:
    database.save_record("campaigns", campaign.id, campaign.model_dump(mode="json"))
    for index, existing in enumerate(campaigns):
        if existing.id == campaign.id:
            campaigns[index] = campaign
            break
    return campaign


def save_customer(customer: Customer) -> Customer:
    database.save_record("customers", customer.id, customer.model_dump(mode="json"))
    for index, existing in enumerate(customers):
        if existing.id == customer.id:
            customers[index] = customer
            break
    return customer


def create_segment(payload: SegmentCreate, customer_count: int, sample_customer_ids: list[str]) -> Segment:
    segment = Segment(id=f"seg-{uuid4().hex[:8]}", updated_at=date.today(), customer_count=customer_count,
                      sample_customer_ids=sample_customer_ids, estimate_basis="synthetic_sample", **payload.model_dump())
    segments.insert(0, segment)
    database.save_record("segments", segment.id, segment.model_dump(mode="json"))
    return segment


def save_segment(segment: Segment) -> Segment:
    database.save_record("segments", segment.id, segment.model_dump(mode="json"))
    for index, existing in enumerate(segments):
        if existing.id == segment.id:
            segments[index] = segment
            break
    return segment


def create_offer(payload: OfferCreate, actor: str = "Campaign Admin") -> Offer:
    offer = Offer(id=f"off-{uuid4().hex[:8]}", updated_at=date.today(),
                  status_history=[{"status": payload.status, "actor": actor, "reason": "Offer created", "at": datetime.now(timezone.utc).isoformat()}],
                  **payload.model_dump())
    offer = offer.model_copy(update={"version_history": [{"version": 1, "actor": actor,
                                                            "changed_fields": ["created"], "snapshot": offer.model_dump(mode="json"),
                                                            "at": datetime.now(timezone.utc).isoformat()}]})
    offers.insert(0, offer)
    database.save_record("offers", offer.id, offer.model_dump(mode="json"))
    return offer


def save_offer(offer: Offer) -> Offer:
    database.save_record("offers", offer.id, offer.model_dump(mode="json"))
    for index, existing in enumerate(offers):
        if existing.id == offer.id:
            offers[index] = offer
            break
    return offer


def create_scenario(payload: ScenarioCreate) -> Scenario:
    now = datetime.now(timezone.utc)
    scenario = Scenario(id=f"scn-{uuid4().hex[:8]}", created_at=now, updated_at=now, **payload.model_dump())
    scenarios.insert(0, scenario)
    database.save_record("scenarios", scenario.id, scenario.model_dump(mode="json"))
    return scenario


def save_scenario(scenario: Scenario) -> Scenario:
    database.save_record("scenarios", scenario.id, scenario.model_dump(mode="json"))
    for index, existing in enumerate(scenarios):
        if existing.id == scenario.id:
            scenarios[index] = scenario
            break
    return scenario
