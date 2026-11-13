"""Small persistent SQLite store for the Phase 1–2 development environment."""
import json
import os
import sqlite3
from contextvars import ContextVar
from pathlib import Path
from typing import Any

TABLES = (
    "campaigns", "customers", "segments", "offers", "scenarios", "scenario_runs",
    "journeys", "business_rules", "execution_runs", "approvals", "audit_events", "integrations",
    "workspace_users", "workspace_settings", "auth_sessions", "password_resets",
)
GLOBAL_TABLES = ("workspace_tenants",)
_TENANT_ID: ContextVar[str] = ContextVar("campaignnova_tenant_id", default="campaignnova-demo")


def set_tenant(tenant_id: str):
    return _TENANT_ID.set(tenant_id)


def reset_tenant(token) -> None:
    _TENANT_ID.reset(token)


def current_tenant() -> str:
    return _TENANT_ID.get()


def _path() -> Path:
    return Path(os.getenv("CAMPAIGNNOVA_DB_PATH", "./data/campaignnova.sqlite3"))


def connect() -> sqlite3.Connection:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize(seeds: dict[str, list[Any]]) -> None:
    with connect() as db:
        for table in (*TABLES, "module_actions", *GLOBAL_TABLES):
            # Table names come only from the fixed internal tuple above.
            db.execute(f"CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            columns = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            if "tenant_id" not in columns:
                db.execute(f"ALTER TABLE {table} ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'campaignnova-demo'")
        db.execute("CREATE INDEX IF NOT EXISTS idx_campaignnova_tenant ON workspace_users(tenant_id)")
        for table in TABLES:
            for item in seeds[table]:
                payload = item.model_dump(mode="json")
                db.execute(
                    f"INSERT OR IGNORE INTO {table} (id, payload, tenant_id) VALUES (?, ?, ?)",
                    (str(payload["id"]), json.dumps({**payload, "tenant_id": "campaignnova-demo"}), "campaignnova-demo"),
                )
                existing = db.execute(f"SELECT payload FROM {table} WHERE id = ?", (str(payload["id"]),)).fetchone()
                stored_payload = json.loads(existing["payload"])
                if table == "offers" and stored_payload.get("status") == "Review":
                    stored_payload["status"] = "Pending Approval"
                    db.execute(f"UPDATE {table} SET payload = ? WHERE id = ?",
                               (json.dumps(stored_payload), str(payload["id"])))
                if table == "segments" and str(payload["id"]).startswith("seg-0"):
                    seed_rules = payload.get("rules", {})
                    stored_rules = stored_payload.get("rules", {})
                    if seed_rules.get("conditions") and not stored_rules.get("conditions"):
                        stored_payload.update({"rules": seed_rules, "estimate_basis": "seed_estimate", "sample_customer_ids": [],
                                               "customer_count": payload.get("customer_count", stored_payload.get("customer_count", 0))})
                        db.execute(f"UPDATE {table} SET payload = ? WHERE id = ?",
                                   (json.dumps(stored_payload), str(payload["id"])))
                missing = {key: value for key, value in payload.items() if key not in stored_payload}
                if missing:
                    db.execute(f"UPDATE {table} SET payload = ? WHERE id = ?",
                               (json.dumps({**stored_payload, **missing}), str(payload["id"])))


def list_records(table: str, tenant_id: str | None = None) -> list[dict[str, Any]]:
    if table not in (*TABLES, "module_actions", *GLOBAL_TABLES):
        raise ValueError("Unknown CampaignNova data table")
    scope = tenant_id or current_tenant()
    with connect() as db:
        if scope == "*":
            records = db.execute(f"SELECT payload, tenant_id FROM {table} ORDER BY rowid").fetchall()
        else:
            records = db.execute(f"SELECT payload, tenant_id FROM {table} WHERE tenant_id = ? ORDER BY rowid", (scope,)).fetchall()
    output = []
    for record in records:
        payload = json.loads(record["payload"])
        payload.setdefault("tenant_id", record["tenant_id"])
        output.append(payload)
    return output


def save_record(table: str, record_id: str, payload: dict[str, Any]) -> None:
    if table not in (*TABLES, "module_actions", *GLOBAL_TABLES):
        raise ValueError("Unknown CampaignNova data table")
    scope = payload.get("tenant_id") or ("__global__" if table in GLOBAL_TABLES else current_tenant())
    row = {**payload, "tenant_id": scope}
    # IDs used by singleton settings and seed examples can repeat in separate workspaces.
    physical_id = str(record_id) if scope in {"campaignnova-demo", "__global__"} else f"{scope}:{record_id}"
    with connect() as db:
        db.execute(
            f"INSERT OR REPLACE INTO {table} (id, payload, tenant_id) VALUES (?, ?, ?)",
            (physical_id, json.dumps(row, default=str), scope),
        )


def global_record(table: str, record_id: str) -> dict[str, Any] | None:
    if table not in (*TABLES, "module_actions", *GLOBAL_TABLES):
        raise ValueError("Unknown CampaignNova data table")
    with connect() as db:
        row = db.execute(f"SELECT payload FROM {table} WHERE id = ?", (record_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def add_action(payload: dict[str, Any]) -> None:
    save_record("module_actions", payload["id"], payload)
