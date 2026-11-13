# CampaignNova architecture and module map

## Runtime shape

- **Web:** Next.js, React, TypeScript, Tailwind, accessible shared components. Browser requests go through typed REST clients.
- **API:** Python/FastAPI owns validation, authorization, business rules, and persistence. Keep routers, schemas, services, and repositories separate.
- **Data:** Phase 1 uses a persistent local SQLite database for a simple runnable seed environment. PostgreSQL is the production system of record planned for the enterprise phase. Redis/Celery can be introduced for asynchronous execution; ClickHouse and pgvector remain optional scale-stage components.
- **External systems:** connector/adaptor interfaces isolate CRM, billing, messaging, and LLM providers. Development uses synthetic data and simulated channel adapters.
- **Operations:** environment-based config, Docker Compose, structured logs, health/ready endpoints, migrations, and generated OpenAPI documentation.

## Suggested repository layout

```text
CampaignNova/
├── frontend/
│   ├── app/                    # route pages and layouts by module
│   ├── components/             # shared shell, forms, tables, charts
│   ├── features/               # scenarios/, campaigns/, customers/, audiences/, offers/, journeys/
│   ├── lib/api/                # typed REST client and error handling
│   ├── lib/auth/               # session and permission helpers
│   ├── styles/                 # design tokens and global styles
│   └── public/brand/           # logo variants, app icon, favicon
├── backend/
│   ├── app/api/v1/             # routers grouped by domain
│   ├── app/core/               # settings, security, logging
│   ├── app/models/             # persistence entities
│   ├── app/schemas/            # request/response validation
│   ├── app/services/           # business rules and orchestration
│   ├── app/repositories/       # database access
│   ├── app/integrations/       # CRM, channels, LLM provider adapters
│   ├── app/workers/            # async jobs, retries, execution tasks
│   ├── migrations/             # database migrations
│   └── seed/                   # synthetic development data
├── docs/                       # roadmap, API/module contracts, runbooks
├── infra/                      # compose and deployment configuration
└── .env.example                # names only; never commit credentials
```

Use domain-based naming consistently. Avoid a single giant page/component or router. Keep campaign, customer, audience, offer, journey, execution, identity, and audit concepts in separate modules while sharing only stable contracts.

## Initial domain boundaries

- **Campaigns:** campaign, version, audience reference, offer reference, channel plan, schedule, status history.
- **Customers:** masked profile, subscription, usage/revenue observations, consent, suppression, interaction timeline.
- **Audiences:** segment definition, nested rule groups, preview snapshot, membership mode.
- **Offers:** product/price/validity, eligibility, channel restrictions, limits, version and approval.
- **Journeys and execution:** graph definition, node config, execution instance, customer execution, delivery attempt.
- **Governance:** organization, user, role, permission, approval, audit event, retention policy.
- **Integrations and AI:** connector configuration, sync/job status, provider abstraction, recommendation explanation and approval record.

Tenant IDs belong on tenant-owned records and are enforced server-side for every read/write. PII masking is based on permission and purpose; suppression and consent checks are part of eligibility and execution, not just UI display.
