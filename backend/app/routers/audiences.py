from datetime import date
from uuid import uuid4
from fastapi import APIRouter, HTTPException, Query
from .. import store
from ..schemas import Segment, SegmentCreate, SegmentRuleGroup
from ..services.segmentation import matches, segment_members

router = APIRouter(tags=["audiences"])


def _preview(rules: SegmentRuleGroup):
    return [customer for customer in store.get_customers() if matches(customer, rules)]


def _refresh_dynamic(segment: Segment) -> Segment:
    if segment.mode != "Dynamic":
        return segment
    matches = segment_members(segment, store.get_customers())
    updated = segment.model_copy(update={"customer_count": len(matches), "sample_customer_ids": [c.id for c in matches[:10]], "estimate_basis": "synthetic_sample"})
    return store.save_segment(updated)


@router.get("/segments")
def list_segments(q: str | None = Query(default=None, max_length=120)):
    result = store.get_segments()
    if q:
        result = [s for s in result if q.lower() in s.name.lower() or q.lower() in s.description.lower()]
    return [_refresh_dynamic(s).model_dump(mode="json") for s in result]


@router.get("/segments/{segment_id}")
def get_segment(segment_id: str):
    segment = next((s for s in store.get_segments() if s.id == segment_id), None)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    return _refresh_dynamic(segment).model_dump(mode="json")


@router.post("/segments/estimate")
def estimate_segment(rules: SegmentRuleGroup):
    matches = _preview(rules)
    return {"estimated_customers": len(matches), "sample_total": len(store.get_customers()),
            "sample_customer_ids": [c.id for c in matches[:10]], "basis": "synthetic_sample",
            "message": "Estimate counts the local synthetic sample only, not a production audience."}


@router.post("/segments", response_model=Segment, status_code=201)
def create_segment(payload: SegmentCreate):
    if any(s.name.casefold() == payload.name.casefold() for s in store.get_segments()):
        raise HTTPException(status_code=409, detail="A segment with this name already exists")
    matches = _preview(payload.rules)
    return store.create_segment(payload, len(matches), [c.id for c in matches[:10]])


@router.put("/segments/{segment_id}", response_model=Segment)
def update_segment(segment_id: str, payload: SegmentCreate):
    current = next((s for s in store.get_segments() if s.id == segment_id), None)
    if current is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    if any(s.name.casefold() == payload.name.casefold() and s.id != segment_id for s in store.get_segments()):
        raise HTTPException(status_code=409, detail="A segment with this name already exists")
    matches = _preview(payload.rules)
    updated = Segment(id=current.id, updated_at=date.today(), customer_count=len(matches),
                      sample_customer_ids=[c.id for c in matches[:10]], estimate_basis="synthetic_sample", **payload.model_dump())
    return store.save_segment(updated)
