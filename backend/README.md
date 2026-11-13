# CampaignNova API

FastAPI service. Seed data is synthetic and stored in a local SQLite database at `backend/data/campaignnova.sqlite3` by default. Accounts use salted PBKDF2 password hashes, HTTP-only sessions, and role/department API checks. Tenant isolation, PostgreSQL deployment, and external channel integrations remain deployment work.

## Run locally

```sh
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000/docs` for interactive API documentation. Set `NEXT_PUBLIC_API_URL=http://localhost:8000/api` in the frontend environment.

Open `http://localhost:3000/signup` to bootstrap the first Super Admin account. Later signups require administrator approval. See [`docs/AUTHENTICATION.md`](../docs/AUTHENTICATION.md) for role scopes, profile photos, and SMTP reset delivery.

Set `CAMPAIGNNOVA_DB_PATH` to change the SQLite database file. Docker Compose mounts `backend/data/` so records persist across container restarts.

## Nova Gemini assistant

The backend can call Google's Gemini Developer API using `GEMINI_API_KEY`; the key is only read by the API container and is never sent to the browser or stored in SQLite. The adapter is pinned to `gemini-3.8-flash`, currently listed with free-tier access, to avoid accidentally selecting a paid model. Create a key in [Google AI Studio](https://aistudio.google.com/app/apikey). For Docker Compose, copy `.env.example` to `.env`, set `GEMINI_API_KEY`, then restart the API. For direct Uvicorn, export `GEMINI_API_KEY` in the shell before starting the backend. Without a key, Nova stays on its local rule/template fallback. Gemini free-tier model access has quotas and can change; Google's terms say free-tier content may be used to improve products. Do not send real subscriber details or confidential campaign information to the free-tier provider. Review your Google project billing and quota settings before enabling it.

## API routes

Routes are grouped under `app/routers/` and mounted below `/api`.

| Router | Endpoints |
|---|---|
| `system.py` | `GET /api/health`, `/api/ready` (SQLite readiness and configured-provider status) |
| `dashboard.py` | `GET /api/dashboard` |
| `campaigns.py` | `GET/POST /api/campaigns`, `GET/PATCH /api/campaigns/{campaign_id}`, `POST /api/campaigns/validate`, `POST /api/campaigns/{campaign_id}/status` |
| `customers.py` | `GET /api/customers`, `GET /api/customers/{customer_id}`, `PATCH /api/customers/{customer_id}/consent` |
| `audiences.py` | `GET/POST /api/segments`, `GET/PUT /api/segments/{segment_id}`, `POST /api/segments/estimate` |
| `offers.py` | `GET/POST /api/offers`, `GET/PATCH /api/offers/{offer_id}`, `POST /api/offers/{offer_id}/status` |
| `scenarios.py` | `GET/POST /api/scenarios`, `POST /api/scenarios/import`, `GET/PUT /api/scenarios/{id}`, `POST /api/scenarios/{id}/preview`, `POST /api/scenarios/{id}/simulate`, `GET /api/scenarios/{id}/runs` |
| `journeys.py` | `GET/POST /api/journeys`, `GET/PUT/DELETE /api/journeys/{id}`, `POST /api/journeys/{id}/validate`, `POST /api/journeys/{id}/preview` |
| `business_rules.py` | CRUD `/api/business-rules`, activation and customer eligibility preview |
| `execution.py` | `/api/execution/runs` create/list/detail, pause/resume/retry simulation controls |
| `approvals.py` | `GET/POST /api/approvals`, `POST /api/approvals/{id}/decision`; decisions append audit events |
| `integrations.py` | `GET /api/integrations`, `POST /api/integrations/{connector_id}/check` (catalog/readiness only; no live connection) |
| `ai.py` | `GET /api/ai/status`, `POST /api/ai/assist` (Google Gemini when configured; local templates otherwise) |
| `authentication.py` | Setup status, signup, login/logout, profile and avatar, password change, one-time reset flow |
| `administration.py` | Admin-only role/department catalog, account provisioning/approval, and workspace settings |
| `intelligence.py` | `GET /api/intelligence/overview`, `/cohorts`, `/campaign-comparison`, `/offer-fit`, `/signals` |
| `reports.py` | Report definitions/data and schedule metadata under `/api/reports`; no background scheduler or email delivery |
| `experiments.py` | `GET/POST /api/experiments`, `GET/PUT/DELETE /api/experiments/{id}`, `POST /api/experiments/{id}/preview`; preview only, no measured outcomes |
| `workspaces.py` | `GET /api/modules`, `GET /api/modules/{module_key}`, `POST /api/modules/{module_key}/actions` |

Every navigation module has a workspace key. Authentication routes and system health are public; domain and administration routes require a valid account session. Department and read-only role scopes are enforced by the API. The first local signup creates the Super Admin; later public signups wait for approval. Execution endpoints persist deterministic local simulations only. Configure SMTP for reset emails; otherwise only development mode shows a reset link.

Campaign filters: optional `status` and `q`. Customer filters: optional `q` and `segment`. Segment filter: optional `q`.
