# CampaignNova Web

The Next.js frontend uses the FastAPI service through `lib/api.ts`. Module screens are routed through the shared App Router shell; module-specific API results and capability states are loaded from `/api/modules/{module_key}`.

## Run locally

```sh
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL` to the API base including `/api`, for example `http://localhost:8000/api`.

## Key folders

- `app/` — dashboard, shared layout, and module route.
- `components/` — application shell and shared navigation.
- `features/` — campaign, customer, audience, offers, journey, governance, intelligence and reporting screens grouped by module.
- `lib/` — API client and navigation registry.

Dashboard metrics, campaign rows, and channel rates come from the API. Phase 3–4 screens include journeys, rules, execution simulations, approvals, reports, experiments, administration, and settings. Intelligence screens label synthetic records and descriptive or rule-based results; Nova uses Gemini only when the backend key is configured, otherwise it uses local templates. The UI does not claim real provider delivery or evaluated predictive models.
