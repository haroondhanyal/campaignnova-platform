# Phase 3 module contracts

Phase 3 adds API-backed orchestration, local execution simulation, business rules, approval review, and audit history. Records use the same SQLite development store as Phases 1 and 2.

## Journey Orchestration

- API: `GET/POST /api/journeys`, `GET/PUT/DELETE /api/journeys/{id}`, `POST /api/journeys/{id}/validate`, `POST /api/journeys/{id}/preview`.
- A journey has one trigger, connected nodes, an exit, a version, and an optional saved segment.
- Preview returns a consent-filtered synthetic sample and structural issues. It does not deliver messages or change customer records.

## Business Rules Engine

- API: CRUD at `/api/business-rules`, activation at `PATCH /api/business-rules/{id}/activation`, preview at `POST /api/business-rules/{id}/evaluate/{customer_id}`.
- Conditions support customer value, data usage, churn risk, segment, preferred channel, and consent. Rules also support frequency caps and UTC quiet hours.
- Active rules suppress customers from campaign simulation. Evaluation and simulation do not send messages.

## Campaign Execution

- API: `GET/POST /api/execution/runs`, `GET /api/execution/runs/{id}`, and per-run `pause`, `resume`, and `retry` actions.
- Runs require an approved or scheduled campaign, use an idempotency key, enforce batch/rate limits, and persist customer-level attempts.
- Outcomes are deterministic local adapter results labeled `SIMULATION`; no SMS, WhatsApp, push, email, or other provider is called.

## Approvals and audit

- API: `GET/POST /api/approvals` and `POST /api/approvals/{id}/decision`.
- Campaign, offer, and scenario drafts can be submitted; approver role and requester separation are checked by the development API. Decisions and major rule, journey, and execution actions are persisted in `/api/modules/audit-logs` data.
- Authenticated cookie sessions and department/role checks are enforced for local workspace APIs. They do not provide SSO/MFA or tenant isolation; approval actor identity is taken from the signed-in account.

## Integration boundary

The catalog is available at `GET /api/integrations`; `POST /api/integrations/{connector_id}/check` reports that checks are unavailable until secure settings are configured. The current Phase 3 simulator has no external integrations configured. Provider credentials, secure secret storage, production queue workers, and live delivery remain deployment/integration work and are not represented as connected capabilities.
