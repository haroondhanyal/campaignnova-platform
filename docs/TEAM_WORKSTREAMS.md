# Nine developer workstreams

These are parallel ownership areas. Agree on API contracts and shared design tokens before coding across boundaries. Each owner keeps their module independently reviewable and integrates through documented interfaces.

| Developer | Workstream | Primary ownership | Integration contract |
|---|---|---|---|
| 1 | Platform and architecture | Repo conventions, environment config, Docker/compose, API standards, CI-ready structure | Shared config, health checks, contribution guide |
| 2 | Frontend shell and design system | Brand, logo assets, responsive shell, navigation, theme, shared UI primitives | Tokens/components, route and permission conventions |
| 3 | Dashboard and analytics | Executive overview, campaign trends, metrics, reports and exports | Dashboard/report APIs; metric definitions and observed-vs-estimated labels |
| 4 | Campaign lifecycle and scenarios | Campaign Studio, Scenario Studio, calendar, status transitions and scenario simulations | Campaign/scenario CRUD, lifecycle, validation and preview APIs |
| 5 | Customer and audience | Customer 360, consent/suppression display, segment builder, audience previews | Customer/segment APIs, PII masking rules |
| 6 | Offers and channels | Offer catalog, channel configuration screens, provider adapter interfaces | Offer CRUD/eligibility and channel capability APIs |
| 7 | Journey and execution | Journey canvas, execution orchestration, monitoring, retries | Journey/execution APIs and event/status schema |
| 8 | AI and predictive intelligence | Nova AI workspace/provider abstraction, recommendations, model evaluation | AI request/response schema with explanation, provenance, approval gates |
| 9 | Security, governance, and integration | Auth/RBAC, tenant boundaries, approvals, audit, integration hub | Identity/permission, audit, approval, connector contracts |

## Coordination

- Workstream owners do not create overlapping versions of shared types or design tokens; one agreed source is maintained by Developers 1 and 2.
- Backend endpoints are versioned/documented before dependent screens integrate.
- Each owner contributes a short module README: purpose, user stories, data model, APIs, business rules, and acceptance criteria.
- The team integrates in phase order: Developer 1 and 2 establish the shell; 3–6 build core operations; 7 and 9 add governed orchestration; 8 and 3 deliver intelligence and analytics.

## Current delivery ownership status

- Phase 2 campaign, customer/audience, offer, calendar, and scenario screens are API-backed. Draft campaign and offer activation now goes through the shared approval queue.
- Phase 3 work is integrated across journey editing/preview, rule management/suppression, local execution simulation, approvals/audit, and the connector catalog.
- Phase 4 work is integrated across Nova local assistance, descriptive intelligence, report export/schedule metadata, and the A/B experiment planner.
- Account sign-in, local RBAC, and department access are integrated. SSO/MFA, email verification, production rate limiting, secure provider credentials, and live integrations require deployment work.
