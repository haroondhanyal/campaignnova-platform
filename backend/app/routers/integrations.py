"""Read-only connector catalog. Credentials and external systems are not configured here."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/integrations", tags=["integrations"])
CONNECTORS = [
    {"id": "customer-data", "name": "Customer data platform", "category": "Data", "status": "Not configured", "requirements": "Tenant endpoint, service identity, and field mapping"},
    {"id": "sms", "name": "SMS gateway", "category": "Channel", "status": "Not configured", "requirements": "Provider account, sender ID, credentials, and delivery callback"},
    {"id": "whatsapp", "name": "WhatsApp Business", "category": "Channel", "status": "Not configured", "requirements": "Business account, approved templates, credentials, and webhook"},
    {"id": "push", "name": "Push notifications", "category": "Channel", "status": "Not configured", "requirements": "Application keys, consent mapping, and delivery callback"},
    {"id": "analytics", "name": "Analytics warehouse", "category": "Analytics", "status": "Not configured", "requirements": "Read-only connection, governed dataset, and metric definitions"},
]


@router.get("")
def list_integrations():
    return {"mode": "catalog_only", "connectors": CONNECTORS,
            "message": "No external integrations are connected. Credentials must be configured in a secure deployment environment."}


@router.post("/{connector_id}/check")
def check_integration(connector_id: str):
    connector = next((item for item in CONNECTORS if item["id"] == connector_id), None)
    if connector is None:
        raise HTTPException(404, "Connector not found")
    return {"connector_id": connector_id, "status": "not_configured", "checked": False,
            "message": "A connection check cannot run until secure credentials and endpoint settings are configured."}
