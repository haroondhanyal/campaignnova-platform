from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator


class CampaignStatus(StrEnum):
    DRAFT = "Draft"
    PENDING = "Pending Approval"
    APPROVED = "Approved"
    SCHEDULED = "Scheduled"
    RUNNING = "Running"
    PAUSED = "Paused"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    objective: str = "Retention"
    campaign_type: str = "Retention"
    business_unit: str = "Mobile"
    owner: str = "Campaign Admin"
    priority: Literal["Low", "Normal", "High", "Urgent"] = "Normal"
    channel: str = "SMS"
    audience: str = "All eligible customers"
    segment_id: str | None = None
    imported_audience_id: str | None = None
    offer_id: str | None = None
    message_template: str = Field(default="", max_length=1600)
    start_date: date | None = None
    end_date: date | None = None
    budget: float = Field(default=0, ge=0)
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: CampaignStatus = CampaignStatus.DRAFT

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Campaign end date must be on or after its start date")
        if self.segment_id and self.imported_audience_id:
            raise ValueError("Choose a saved segment or an imported audience, not both")
        if self.imported_audience_id and not self.message_template.strip():
            raise ValueError("Add a message template for the imported audience campaign")
        return self


class CampaignPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    objective: str | None = None
    campaign_type: str | None = None
    business_unit: str | None = None
    owner: str | None = None
    priority: Literal["Low", "Normal", "High", "Urgent"] | None = None
    channel: str | None = None
    audience: str | None = None
    segment_id: str | None = None
    imported_audience_id: str | None = None
    offer_id: str | None = None
    message_template: str | None = Field(default=None, max_length=1600)
    start_date: date | None = None
    end_date: date | None = None
    budget: float | None = Field(default=None, ge=0)
    tags: list[str] | None = Field(default=None, max_length=20)


class CampaignTransition(BaseModel):
    status: CampaignStatus
    actor: str = Field(default="Campaign Admin", min_length=2, max_length=120)
    reason: str = Field(default="", max_length=500)


class Campaign(CampaignCreate):
    id: str
    created_at: datetime
    reached: int = 0
    conversions: int = 0
    revenue: float = 0
    status_history: list[dict[str, Any]] = Field(default_factory=list)


class Customer(BaseModel):
    id: str
    name: str
    identifier: str
    customer_type: str = "Prepaid"
    subscription_status: str = "Active"
    account_type: str = "Individual"
    segment: str
    plan: str
    tenure_days: int = 0
    monthly_value: float
    recharge_history: list[dict[str, Any]] = Field(default_factory=list)
    data_usage_gb: float = 0
    voice_usage_minutes: int = 0
    sms_usage: int = 0
    revenue_history: list[dict[str, Any]] = Field(default_factory=list)
    lifetime_value: float = 0
    engagement_history: list[dict[str, Any]] = Field(default_factory=list)
    campaign_participation: list[str] = Field(default_factory=list)
    redeemed_offers: list[str] = Field(default_factory=list)
    preferred_channel: str = "SMS"
    churn_risk: str
    consent: bool
    consent_history: list[dict[str, Any]] = Field(default_factory=list)
    updated_at: datetime | None = None


class CustomerConsentUpdate(BaseModel):
    consent: bool
    reason: str = Field(default="Preference updated by an authorized operator", max_length=300)


class SegmentCondition(BaseModel):
    field: Literal["customer_type", "subscription_status", "segment", "plan", "tenure_days", "monthly_value", "data_usage_gb", "voice_usage_minutes", "churn_risk", "consent"]
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "contains", "in"]
    value: str | float | int | bool | list[str | float | int | bool]


class SegmentRuleGroup(BaseModel):
    combinator: Literal["AND", "OR"] = "AND"
    conditions: list[SegmentCondition] = Field(default_factory=list)
    groups: list["SegmentRuleGroup"] = Field(default_factory=list)


SegmentRuleGroup.model_rebuild()


class SegmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    mode: Literal["Dynamic", "Static"] = "Dynamic"
    rules: SegmentRuleGroup = Field(default_factory=SegmentRuleGroup)


class Segment(SegmentCreate):
    id: str
    customer_count: int = 0
    updated_at: date
    sample_customer_ids: list[str] = Field(default_factory=list)
    estimate_basis: Literal["seed_estimate", "synthetic_sample"] = "seed_estimate"


class OfferCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    product: str = "Data bundle"
    price: float = Field(ge=0)
    validity_days: int = Field(gt=0, le=3650)
    eligibility: str = "All eligible customers"
    start_date: date | None = None
    end_date: date | None = None
    channel_restrictions: list[str] = Field(default_factory=list)
    redemption_limit: int | None = Field(default=None, gt=0)
    priority: int = Field(default=100, ge=1, le=1000)
    status: Literal["Draft", "Pending Approval", "Active", "Expired"] = "Draft"

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Offer end date must be on or after its start date")
        return self


class Offer(OfferCreate):
    id: str
    updated_at: date | None = None
    version: int = 1
    status_history: list[dict[str, Any]] = Field(default_factory=list)
    version_history: list[dict[str, Any]] = Field(default_factory=list)


class OfferPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    product: str | None = None
    price: float | None = Field(default=None, ge=0)
    validity_days: int | None = Field(default=None, gt=0, le=3650)
    eligibility: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    channel_restrictions: list[str] | None = None
    redemption_limit: int | None = Field(default=None, gt=0)
    priority: int | None = Field(default=None, ge=1, le=1000)


class OfferStatusUpdate(BaseModel):
    status: Literal["Pending Approval", "Active", "Expired", "Draft"]
    actor: str = Field(default="Campaign Admin", min_length=2, max_length=120)
    reason: str = Field(default="", max_length=500)


class ScenarioCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    objective: str = "Retention"
    segment_id: str | None = None
    offer_id: str | None = None
    channel: Literal["SMS", "WhatsApp", "USSD", "Push", "Email", "In-App"] = "SMS"
    message_template: str = Field(default="", max_length=1600)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Scenario end date must be on or after its start date")
        return self


class Scenario(ScenarioCreate):
    id: str
    status: Literal["Draft", "Ready", "Archived"] = "Draft"
    version: int = 1
    created_at: datetime
    updated_at: datetime | None = None


class ScenarioRun(BaseModel):
    id: str
    scenario_id: str
    status: Literal["Simulated"] = "Simulated"
    eligible_count: int
    excluded_no_consent: int
    sample_customer_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    idempotency_key: str
    scenario_version: int
    messages_sent: int = 0


class ScenarioSimulationRequest(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
