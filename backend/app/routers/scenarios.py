from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, HTTPException
from .. import database, store
from ..schemas import Scenario, ScenarioCreate, ScenarioRun, ScenarioSimulationRequest
from ..services.segmentation import segment_members

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _get_scenario(scenario_id: str) -> Scenario:
    scenario = next((item for item in store.get_scenarios() if item.id == scenario_id), None)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


def _validate_references(payload: ScenarioCreate) -> None:
    if payload.segment_id and not any(segment.id == payload.segment_id for segment in store.get_segments()):
        raise HTTPException(status_code=422, detail="Selected segment was not found")
    if payload.offer_id:
        offer = next((item for item in store.get_offers() if item.id == payload.offer_id), None)
        if offer is None:
            raise HTTPException(status_code=422, detail="Selected offer was not found")
        if offer.status != "Active":
            raise HTTPException(status_code=422, detail="Select an active offer")


def _audience(scenario: Scenario):
    segment = next((item for item in store.get_segments() if item.id == scenario.segment_id), None) if scenario.segment_id else None
    if segment is None:
        target = list(store.get_customers())
    else:
        target = segment_members(segment, store.get_customers())
    eligible = [customer for customer in target if customer.consent]
    excluded = [customer for customer in target if not customer.consent]
    return target, eligible, excluded


def _message_preview(scenario: Scenario, customer, offer_name: str) -> str:
    template = scenario.message_template or "Hello {{name}}, view your available offer in the app."
    return template.replace("{{name}}", customer.name).replace("{{offer_name}}", offer_name)


def _preview(scenario: Scenario):
    target, eligible, excluded = _audience(scenario)
    offer = next((item for item in store.get_offers() if item.id == scenario.offer_id), None) if scenario.offer_id else None
    channel_allowed = not offer or not offer.channel_restrictions or scenario.channel in offer.channel_restrictions
    samples = [{
        "customer_id": customer.id,
        "name": customer.name,
        "masked_subscriber_number": customer.identifier,
        "consent": customer.consent,
        "preferred_channel": customer.preferred_channel,
        "channel_matches_preference": customer.preferred_channel == scenario.channel,
        "segment": customer.segment,
        "monthly_value_pkr": customer.monthly_value,
        "data_usage_gb": customer.data_usage_gb,
        "churn_risk": customer.churn_risk,
        "sample_message": _message_preview(scenario, customer, offer.name if offer else "your offer"),
    } for customer in eligible[:12]]
    return {
        "scenario_id": scenario.id,
        "target_count": len(target),
        "eligible_count": len(eligible),
        "excluded_no_consent": len(excluded),
        "sample_customers": samples,
        "sample_total": len(store.get_customers()),
        "basis": "synthetic_sample",
        "channel": scenario.channel,
        "offer": offer.name if offer else None,
        "offer_channel_allowed": channel_allowed,
        "warnings": (["No eligible customers in the sample"] if not eligible else [])
                    + (["Offer channel restriction does not include the selected channel"] if not channel_allowed else []),
        "delivery": "preview_only",
        "message": "This preview uses masked synthetic subscriber numbers. No messages are sent.",
    }


@router.get("")
def list_scenarios(q: str | None = None, status: str | None = None):
    rows = store.get_scenarios()
    if q:
        rows = [item for item in rows if q.casefold() in item.name.casefold() or q.casefold() in item.objective.casefold()]
    if status:
        rows = [item for item in rows if item.status == status]
    result = []
    for scenario in rows:
        preview = _preview(scenario)
        result.append({**scenario.model_dump(mode="json"), "eligible_count": preview["eligible_count"],
                       "excluded_no_consent": preview["excluded_no_consent"], "basis": preview["basis"]})
    return result


@router.post("", response_model=Scenario, status_code=201)
def create_scenario(payload: ScenarioCreate):
    _validate_references(payload)
    if any(item.name.casefold() == payload.name.casefold() for item in store.get_scenarios()):
        raise HTTPException(status_code=409, detail="A scenario with this name already exists")
    return store.create_scenario(payload)


@router.post("/import", response_model=Scenario, status_code=201)
def import_scenario(payload: ScenarioCreate):
    """Import a scenario definition JSON; raw customer contact lists are not accepted here."""
    return create_scenario(payload)


@router.get("/{scenario_id}", response_model=Scenario)
def get_scenario(scenario_id: str):
    return _get_scenario(scenario_id)


@router.put("/{scenario_id}", response_model=Scenario)
def update_scenario(scenario_id: str, payload: ScenarioCreate):
    current = _get_scenario(scenario_id)
    if current.status != "Draft":
        raise HTTPException(status_code=409, detail="Only draft scenarios can be edited")
    _validate_references(payload)
    if any(item.id != scenario_id and item.name.casefold() == payload.name.casefold() for item in store.get_scenarios()):
        raise HTTPException(status_code=409, detail="A scenario with this name already exists")
    updated = Scenario(id=current.id, status=current.status, version=current.version + 1,
                       created_at=current.created_at, updated_at=datetime.now(timezone.utc), **payload.model_dump())
    return store.save_scenario(updated)


@router.post("/{scenario_id}/preview")
def preview_scenario(scenario_id: str):
    return _preview(_get_scenario(scenario_id))


@router.post("/{scenario_id}/simulate", response_model=ScenarioRun)
def simulate_scenario(scenario_id: str, payload: ScenarioSimulationRequest):
    scenario = _get_scenario(scenario_id)
    existing = next((row for row in database.list_records("scenario_runs") if row.get("idempotency_key") == payload.idempotency_key), None)
    if existing:
        if existing["scenario_id"] != scenario.id:
            raise HTTPException(status_code=409, detail="Idempotency key was already used for another scenario")
        return existing
    preview = _preview(scenario)
    run = ScenarioRun(id=f"run-{uuid4().hex[:10]}", scenario_id=scenario.id, eligible_count=preview["eligible_count"],
                      excluded_no_consent=preview["excluded_no_consent"],
                      sample_customer_ids=[item["customer_id"] for item in preview["sample_customers"]],
                      created_at=datetime.now(timezone.utc), idempotency_key=payload.idempotency_key,
                      scenario_version=scenario.version, messages_sent=0)
    database.save_record("scenario_runs", run.id, run.model_dump(mode="json"))
    return run


@router.get("/{scenario_id}/runs", response_model=list[ScenarioRun])
def list_scenario_runs(scenario_id: str):
    _get_scenario(scenario_id)
    return [ScenarioRun.model_validate(row) for row in database.list_records("scenario_runs") if row.get("scenario_id") == scenario_id]
