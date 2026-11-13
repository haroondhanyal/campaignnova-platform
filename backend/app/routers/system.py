from fastapi import APIRouter
from .. import database
from ..services import gemini

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "campaignnova-api", "data_mode": "synthetic-sqlite", "api_version": "0.6.0"}


@router.get("/ready")
def ready():
    with database.connect() as db:
        db.execute("SELECT 1").fetchone()
    counts = {table: len(database.list_records(table)) for table in ("campaigns", "customers", "segments", "offers")}
    return {"status": "ready", "database": "sqlite", "seed_record_counts": counts,
            "gemini_configured": gemini.configured(), "live_channel_providers": 0,
            "execution_mode": "simulation_only", "authentication": "session-cookie-rbac"}
