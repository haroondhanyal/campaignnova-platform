"""Local campaign execution simulator. It never contacts a provider."""
import base64
import csv
import io
import posixpath
import re
import zipfile
from datetime import datetime, timezone
from uuid import uuid4
import xml.etree.ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .. import database, store
from ..services.segmentation import segment_members
from ..services.audit import record_audit_event
from .authentication import require_user

router = APIRouter(prefix="/execution", tags=["execution"])
CHANNELS = {"SMS", "WhatsApp", "USSD", "Push", "Email", "In-App"}


class StartRun(BaseModel):
    campaign_id: str
    idempotency_key: str = Field(min_length=8, max_length=120)
    batch_size: int = Field(default=25, ge=1, le=500)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)


class AudienceImportRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=180)
    file_data: str = Field(min_length=40, max_length=7_000_000)
    phone_country_code: str = Field(default="+92", pattern=r"^\+[1-9]\d{0,3}$")
    consent_confirmed: bool = False


def _xlsx_rows(content: bytes) -> list[list[str]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except (zipfile.BadZipFile, OSError):
        raise HTTPException(422, "This XLSX file is not a valid Excel workbook") from None
    with archive:
        entries = archive.infolist()
        if sum(item.file_size for item in entries) > 25 * 1024 * 1024:
            raise HTTPException(413, "Excel workbook expands beyond the 25 MB processing limit")
        names = set(archive.namelist())
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.iter() if node.tag.endswith("}t") or node.tag == "t")
                      for item in root if item.tag.endswith("}si") or item.tag == "si"]
        sheet_path = "xl/worksheets/sheet1.xml"
        if "xl/workbook.xml" in names and "xl/_rels/workbook.xml.rels" in names:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            first_sheet = next((node for node in workbook.iter() if node.tag.endswith("}sheet") or node.tag == "sheet"), None)
            if first_sheet is not None:
                relation_id = next((value for key, value in first_sheet.attrib.items() if key.endswith("}id") or key == "id"), None)
                rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
                target = next((node.attrib.get("Target") for node in rel_root
                               if node.attrib.get("Id") == relation_id), None)
                if target:
                    sheet_path = posixpath.normpath(target.lstrip("/") if target.startswith("/")
                                                    else posixpath.join("xl", target))
        if sheet_path not in names:
            raise HTTPException(422, "The first worksheet could not be found in this workbook")
        sheet = ET.fromstring(archive.read(sheet_path))
        rows: list[list[str]] = []
        for row in (node for node in sheet.iter() if node.tag.endswith("}row") or node.tag == "row"):
            cells: dict[int, str] = {}
            for cell in (node for node in row if node.tag.endswith("}c") or node.tag == "c"):
                reference = cell.attrib.get("r", "")
                letters = re.match(r"[A-Z]+", reference.upper())
                if not letters:
                    continue
                column = 0
                for char in letters.group(0):
                    column = column * 26 + ord(char) - 64
                column -= 1
                cell_type = cell.attrib.get("t")
                value_node = next((node for node in cell if node.tag.endswith("}v") or node.tag == "v"), None)
                value = value_node.text or "" if value_node is not None else ""
                if cell_type == "s" and value:
                    try:
                        value = shared[int(value)]
                    except (ValueError, IndexError):
                        value = ""
                elif cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter() if node.tag.endswith("}t") or node.tag == "t")
                cells[column] = str(value)
            if cells:
                rows.append([cells.get(index, "") for index in range(max(cells) + 1)])
            if len(rows) > 10001:
                raise HTTPException(413, "Excel workbook exceeds the 10,000 row limit")
        return rows


def _tabular_rows(filename: str, content: bytes) -> list[dict[str, str]]:
    extension = filename.casefold().rsplit(".", 1)[-1] if "." in filename else ""
    if extension == "xlsx":
        rows = _xlsx_rows(content)
    elif extension == "csv":
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "Save the CSV as UTF-8 and upload it again") from None
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t") if text.strip() else csv.excel
        except csv.Error:
            dialect = csv.excel
        rows = list(csv.reader(io.StringIO(text), dialect))
    else:
        raise HTTPException(415, "Upload an Excel .xlsx or .csv file")
    if len(rows) < 2:
        raise HTTPException(422, "The spreadsheet needs a header row and at least one contact")
    headers = [re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_") for value in rows[0]]
    aliases = {"phone_number", "customer_number", "mobile_number", "msisdn", "phone", "mobile", "contact_number", "number"}
    phone_column = next((index for index, header in enumerate(headers) if header in aliases), None)
    if phone_column is None:
        raise HTTPException(422, "Add a phone_number column to the first row of the spreadsheet")
    consent_aliases = {"consent", "marketing_consent", "opt_in", "opted_in", "consented"}
    consent_column = next((index for index, header in enumerate(headers) if header in consent_aliases), None)
    if len(rows) > 10001:
        raise HTTPException(413, "Spreadsheet exceeds the 10,000 row limit")
    output = []
    for row in rows[1:]:
        if not any(str(value).strip() for value in row):
            continue
        output.append({"phone": str(row[phone_column] if phone_column < len(row) else "").strip(),
                       "consent": str(row[consent_column] if consent_column is not None and consent_column < len(row) else "").strip()
                       if consent_column is not None else None})
    return output


def _e164(raw: str, country_code: str) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if raw.strip().startswith("+"):
        number = f"+{digits}"
    elif digits.startswith("00"):
        number = f"+{digits[2:]}"
    else:
        prefix = country_code[1:]
        if digits.startswith("0"):
            digits = digits[1:]
        if digits.startswith(prefix) and len(digits) > 10:
            number = f"+{digits}"
        else:
            number = f"{country_code}{digits}"
    return number if re.fullmatch(r"\+[1-9]\d{7,14}", number) else None


@router.post("/audiences/import")
def import_audience(payload: AudienceImportRequest, current: dict = Depends(require_user)):
    if not payload.consent_confirmed:
        raise HTTPException(422, "Confirm that these contacts have opted in to receive marketing messages")
    if not re.fullmatch(r"data:[^,]{1,120};base64,[A-Za-z0-9+/=]+", payload.file_data):
        raise HTTPException(422, "Spreadsheet data is not valid base64 content")
    encoded = payload.file_data.split(",", 1)[1]
    try:
        content = base64.b64decode(encoded, validate=True)
    except ValueError:
        raise HTTPException(422, "Spreadsheet data is not valid base64 content") from None
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(413, "Spreadsheet must be 5 MB or smaller")
    raw_rows = _tabular_rows(payload.file_name, content)
    consent_values = {"1", "true", "yes", "y", "opted in", "opted-in", "consented"}
    seen: set[str] = set()
    contacts = []
    invalid_rows = duplicates = 0
    consent_column_present = any(row["consent"] is not None for row in raw_rows)
    for row in raw_rows:
        number = _e164(row["phone"], payload.phone_country_code)
        if not number:
            invalid_rows += 1
            continue
        if number in seen:
            duplicates += 1
            continue
        seen.add(number)
        consent = row["consent"].casefold() in consent_values if consent_column_present else True
        contacts.append({"customer_id": f"imp-{uuid4().hex[:14]}",
                         "identifier": f"{payload.phone_country_code} •••• {number[-4:]}",
                         "consent": consent})
    if not contacts:
        raise HTTPException(422, "No valid phone numbers were found; check the phone_number column")
    audience_id = f"aud-{uuid4().hex[:12]}"
    consented_count = sum(contact["consent"] for contact in contacts)
    record = {"id": audience_id, "file_name": payload.file_name, "total_count": len(contacts),
              "consented_count": consented_count, "excluded_no_consent": len(contacts) - consented_count,
              "invalid_rows": invalid_rows, "duplicates": duplicates, "consent_column_present": consent_column_present,
              "contacts": contacts, "created_at": datetime.now(timezone.utc).isoformat(),
              "tenant_id": database.current_tenant()}
    database.save_record("campaign_audiences", audience_id, record)
    record_audit_event(current["email"], "campaign_audience_imported", "campaign_audience", audience_id,
                       {key: record[key] for key in ("file_name", "total_count", "consented_count", "excluded_no_consent", "invalid_rows", "duplicates")})
    return {"id": audience_id, "file_name": payload.file_name, "total_count": record["total_count"],
            "consented_count": consented_count, "excluded_no_consent": record["excluded_no_consent"],
            "invalid_rows": invalid_rows, "duplicates": duplicates,
            "consent_column_present": consent_column_present,
            "preview": [contact["identifier"] for contact in contacts[:5]],
            "raw_phone_numbers_stored": False}


def _all_runs():
    return database.list_records("execution_runs")


def _save(run):
    run["updated_at"] = datetime.now(timezone.utc).isoformat()
    database.save_record("execution_runs", run["id"], run)
    return run


def _get(run_id):
    run = next((item for item in _all_runs() if item["id"] == run_id), None)
    if not run:
        raise HTTPException(404, "Execution run not found")
    return run


def _process(run, retry=False):
    if run["status"] == "Paused":
        return run
    items = run["customers"]
    if retry:
        pending = [x for x in items if x["status"] == "Simulated Failed" and x["attempts"] < 3]
        limit = min(run["batch_size"], run["rate_limit_per_minute"])
        chosen = pending[:limit]
    else:
        pending = [x for x in items if x["status"] == "Queued"]
        limit = min(run["batch_size"], run["rate_limit_per_minute"])
        chosen = pending[:limit]
    run["batch_number"] += 1
    now = datetime.now(timezone.utc).isoformat()
    # The local adapter is deterministic and intentionally marks cus-1002 as a simulated failure.
    for item in chosen:
        item["attempts"] += 1
        failed = item["customer_id"].endswith("2")
        item["status"] = "Simulated Failed" if failed else "Simulated Delivered"
        item["last_attempt_at"] = now
        item["result"] = "SIMULATION: deterministic adapter failure" if failed else "SIMULATION: accepted by local adapter; no message sent"
        item["history"].append({"attempt": item["attempts"], "status": item["status"], "at": now, "mode": "SIMULATION"})
    if not retry:
        remains = any(x["status"] == "Queued" for x in items)
        run["status"] = "Queued" if remains else "Completed"
    run["summary"] = _counts(run)
    return _save(run)


def _counts(run):
    rows = run["customers"]
    failed = sum(x["status"] == "Simulated Failed" for x in rows)
    return {"targeted": len(rows), "queued": sum(x["status"] == "Queued" for x in rows),
            "simulated_delivered": sum(x["status"] == "Simulated Delivered" for x in rows),
            "failed": failed, "dead_letter": sum(x["status"] == "Simulated Failed" and x["attempts"] >= 3 for x in rows),
            "consent_excluded": run.get("consent_excluded", 0), "rule_excluded": run.get("rule_excluded", 0)}


def _rules_allow(customer, rules, runs, now):
    """Apply active global rules to simulation eligibility; never deliver."""
    for rule in rules:
        conditions = rule.get("conditions", [])
        results = []
        for condition in conditions:
            field, op, expected = condition["field"], condition["operator"], condition["value"]
            value = customer.segment if field == "segment" else getattr(customer, field, None)
            if op == "eq": passed = value == expected
            elif op == "ne": passed = value != expected
            elif op == "contains": passed = str(expected).casefold() in str(value).casefold()
            else:
                try: passed = {"gt": value > expected, "gte": value >= expected, "lt": value < expected, "lte": value <= expected}[op]
                except (TypeError, KeyError): passed = False
            results.append(passed)
        if conditions and not ((all(results) if rule.get("match") == "all" else any(results))):
            return False
        quiet = rule.get("quiet_hours")
        if quiet:
            hour = now.hour
            start, end = quiet["start"], quiet["end"]
            if (start <= hour < end) if start < end else (hour >= start or hour < end):
                return False
        since = now.timestamp() - rule.get("cap_window_days", 7) * 86400
        contacts = sum(1 for run in runs if _run_timestamp(run.get("created_at")) >= since
                       for item in run.get("customers", [])
                       if item.get("customer_id") == customer.id and item.get("attempts", 0) > 0)
        if contacts >= rule.get("frequency_cap", 1):
            return False
    return True


def _run_timestamp(value):
    try: return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError): return 0


@router.get("/runs")
def list_runs():
    return list(reversed(_all_runs()))


@router.post("/runs")
def start_run(payload: StartRun):
    existing = next((r for r in _all_runs() if r.get("idempotency_key") == payload.idempotency_key), None)
    if existing:
        if existing["campaign_id"] != payload.campaign_id:
            raise HTTPException(409, "Idempotency key already belongs to another campaign")
        return existing
    campaign = next((c for c in store.get_campaigns() if c.id == payload.campaign_id), None)
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    if campaign.status not in {"Approved", "Scheduled", "Running"}:
        raise HTTPException(409, "Campaign must be approved, scheduled, or running before simulation")
    if campaign.channel not in CHANNELS:
        raise HTTPException(422, "Campaign channel has no simulation adapter")
    imported_audience = None
    now_dt = datetime.now(timezone.utc)
    if campaign.imported_audience_id:
        imported_audience = next((row for row in database.list_records("campaign_audiences")
                                  if row.get("id") == campaign.imported_audience_id), None)
        if not imported_audience:
            raise HTTPException(422, "Imported audience is no longer available; upload it again")
        target = imported_audience.get("contacts", [])
        excluded = sum(not contact.get("consent") for contact in target)
        eligible = [contact for contact in target if contact.get("consent")]
        rule_excluded = 0
    else:
        target = list(store.get_customers())
        if campaign.segment_id:
            segment = next((s for s in store.get_segments() if s.id == campaign.segment_id), None)
            if not segment:
                raise HTTPException(422, "Campaign segment was not found")
            target = segment_members(segment, target)
        excluded = sum(not customer.consent or customer.subscription_status != "Active" for customer in target)
        base_eligible = [c for c in target if c.consent and c.subscription_status == "Active"]
        active_rules = [rule for rule in database.list_records("business_rules") if rule.get("active")]
        prior_runs = _all_runs()
        eligible = [c for c in base_eligible if _rules_allow(c, active_rules, prior_runs, now_dt)]
        rule_excluded = len(base_eligible) - len(eligible)
    if not eligible:
        raise HTTPException(422, "No active, consented customers are eligible for this simulation")
    now = now_dt.isoformat()
    run = {"id": f"run-{uuid4().hex[:10]}", "campaign_id": campaign.id, "campaign_name": campaign.name,
           "channel": campaign.channel, "mode": "SIMULATION", "status": "Queued", "idempotency_key": payload.idempotency_key,
           "batch_size": payload.batch_size, "rate_limit_per_minute": payload.rate_limit_per_minute, "batch_number": 0,
           "message_template": campaign.message_template, "audience_source": "imported list · consent-only checks" if imported_audience else "workspace sample · consent and rules",
           "consent_excluded": excluded, "rule_excluded": rule_excluded, "created_at": now, "updated_at": now,
           "customers": [{"customer_id": c["customer_id"] if imported_audience else c.id,
                          "identifier": c["identifier"] if imported_audience else c.identifier,
                          "status": "Queued", "attempts": 0,
                          "result": "Awaiting local simulation", "history": []} for c in eligible]}
    run["summary"] = _counts(run)
    database.save_record("execution_runs", run["id"], run)
    record_audit_event("local-simulator", "execution_simulated", "campaign", campaign.id,
                       {"run_id": run["id"], "mode": "SIMULATION", "targeted": len(eligible), "consent_excluded": excluded})
    return _process(run)


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    return _get(run_id)


@router.post("/runs/{run_id}/pause")
def pause_run(run_id: str):
    run = _get(run_id)
    if run["status"] == "Queued":
        run["status"] = "Paused"
    saved = _save(run)
    record_audit_event("local-simulator", "execution_paused", "execution_run", run_id, {"status": saved["status"]})
    return saved


@router.post("/runs/{run_id}/resume")
def resume_run(run_id: str):
    run = _get(run_id)
    if run["status"] == "Paused":
        run["status"] = "Queued"
    if run["status"] == "Queued":
        saved = _process(run)
        record_audit_event("local-simulator", "execution_resumed", "execution_run", run_id, {"status": saved["status"]})
        return saved
    return run


@router.post("/runs/{run_id}/retry")
def retry_run(run_id: str):
    run = _get(run_id)
    if run["status"] == "Paused":
        raise HTTPException(409, "Resume the run before retrying")
    if not any(x["status"] == "Simulated Failed" and x["attempts"] < 3 for x in run["customers"]):
        raise HTTPException(409, "No retryable simulated failures remain")
    saved = _process(run, retry=True)
    record_audit_event("local-simulator", "execution_retried", "execution_run", run_id, {"summary": saved["summary"]})
    return saved
