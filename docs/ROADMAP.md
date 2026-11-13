# CampaignNova delivery roadmap

CampaignNova is delivered in four phases. Each phase leaves a usable increment and keeps simulated providers clearly labeled until real credentials and integrations exist.

## Phase 1 — Foundation and product shell

**Outcome:** a runnable, API-backed application shell with the CampaignNova brand and coherent navigation.

- Establish the frontend, FastAPI backend, environment configuration, and API boundary.
- Define the shared design tokens, typography, logo direction, responsive navigation, light/dark-ready colors, and accessible controls.
- Deliver executive dashboard, global search shell, notifications/profile controls, and module landing screens.
- Add initial database model/migration direction, synthetic seed data, health endpoint, and API documentation.
- Mount domain routers for campaign, customer, audience, offer, dashboard, system, and module workspace APIs; load each navigation screen from its workspace API.
- Keep synthetic dashboard figures and any unconnected sample visuals labeled accurately.

**Acceptance:** frontend and backend start from documented commands; navigation opens every module; dashboard and module views load through APIs; draft campaign creation works through the API; other module actions are recorded and clearly labeled; no real provider integration or AI claim is implied.

## Phase 2 — Core campaign and customer operations

**Outcome:** users can build, review, and manage a campaign using customers, audiences, offers, and a calendar.

- Campaign Studio with draft creation, lifecycle status, validation, and approval handoff.
- Customer 360 with masked identifiers, consent/suppression, usage and campaign timeline.
- Static/dynamic audiences and AND/OR segmentation rules with preview/sample counts.
- Offer catalog, eligibility, validity, approval/version history.
- Campaign calendar, filtering, and campaign detail views.
- Persist records and expose validated REST APIs; add tenant ownership to core entities.

**Phase 2 implementation status:** Campaign drafts, edit/status lifecycle, validation, audience/offer references, calendar queries, searchable customer profiles and consent updates, rule-based synthetic audience previews, saved dynamic/static segments, offer catalog CRUD, and offer approval/version history are implemented against SQLite-backed APIs. See `PHASE_2_MODULE_CONTRACTS.md`.

Scenario Studio also supports JSON scenario import, segment/offer/channel selection, consent-aware masked customer previews, message personalization previews, and persisted idempotent simulations. Simulation does not send messages.

## Phase 3 — Orchestration, execution, and governance

**Outcome:** validated campaigns can run through observable simulated channels with controlled approvals.

- Visual journey builder, business rules, node validation, versioning, and preview.
- Queue-backed execution, customer-level tracking, retry/idempotency, pause/resume, rate limits, and failure handling.
- Simulated SMS/WhatsApp/push/email adapters explicitly marked simulated.
- RBAC, approval workflow, audit events, suppression enforcement, integration hub, and execution monitoring.
- Reporting for observed delivery/conversion metrics; distinguish observed from estimated incremental revenue.

**Phase 3 implementation status:** journey definitions are saved with versions and validated before audience previews; business rules are editable and their active consent, eligibility, frequency-cap, and quiet-hour checks constrain the execution simulator; campaign runs persist batches, per-customer simulated results, retries, pause/resume, idempotency, and audit events; approvals for campaigns, offers, and scenarios enforce requester separation using the signed-in account. Local password authentication and department-based access checks are implemented. The execution adapter is deliberately simulation-only and no external providers are configured. SSO/MFA, tenant isolation, and production queue workers remain deployment work. See `PHASE_3_MODULE_CONTRACTS.md`.

## Phase 4 — Intelligence and enterprise readiness

**Outcome:** explainable AI assistance and deployable enterprise operations.

- Provider-independent Nova AI adapter, natural-language assistance, generated content, and recommendation explanations.
- Churn/propensity/NBO models only after evaluation; display model version and confidence, never invented accuracy.
- Advanced analytics, export/report scheduling, anomaly detection, and cohort/experiment views.
- Harden multi-tenancy, SSO/MFA-ready interfaces, security controls, observability, backup/recovery, deployment, onboarding, and licensing.
- Complete unit, integration, and end-to-end test suites before commercial production claims.

**Phase 4 application status:** the app now has an optional server-side Gemini assistant with a local fallback, descriptive cohort/campaign comparisons, explainable rule-based offer cues, explicit record-review signals, downloadable campaign/channel/cohort/simulation reports, and an A/B experiment planner with consent-filtered allocation previews. Schedule preferences can be stored, but do not run automatically. Workspace administration now provisions real local accounts with role/department access, password reset, and user profiles. These features use synthetic or seeded data and make no model accuracy, causal lift, provider delivery, or statistical anomaly claims. There are not enough labeled longitudinal outcomes to train and evaluate churn, propensity, or next-best-offer models responsibly; the intelligence screen reports that limitation instead of substituting an unvalidated score. Production SSO/MFA, corporate email verification, tenant isolation, external provider integrations, background scheduling, and deployment hardening remain infrastructure work. Gemini remains inactive until `GEMINI_API_KEY` is configured on the backend.

## Delivery rules

- Every module starts with purpose, user stories, data model, API contract, business rules, and acceptance criteria.
- Use synthetic data until connected systems are configured. Label simulated execution and AI behavior honestly.
- Require human approval before any campaign launch; preserve consent, suppression, and audit history.
- Keep frontend screens API-backed and do not connect the browser directly to the database.
