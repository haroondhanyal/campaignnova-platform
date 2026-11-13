from datetime import datetime, timezone
from uuid import uuid4
from .. import database


def record_audit_event(actor: str, action: str, resource_type: str, resource_id: str, details: dict | None = None) -> dict:
    event = {
        "id": f"aud-{uuid4().hex[:12]}",
        "actor": actor,
        "action": action,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "details": details or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    database.save_record("audit_events", event["id"], event)
    return event
