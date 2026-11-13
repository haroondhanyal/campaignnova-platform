# Phase 2 module contracts

All Phase 2 records use the local SQLite persistence layer. The data remains synthetic and the database is a development store. Customer audience estimates explicitly count only the local sample.

## Campaign Studio and Calendar

- **Purpose:** create and manage a campaign draft, validate it, move it through its lifecycle, and find scheduled dates.
- **User stories:** a campaign manager can define the goal, owner, priority, dates, budget, audience, offer and channels; view saved campaigns; request approval; and record an approval or status change. An operator can browse campaigns by calendar month.
- **Data:** `Campaign` includes descriptive fields, target segment/offer references, schedule, budget, current status, delivery aggregates, and a status history with actor/reason/time.
- **APIs:** `GET/POST /api/campaigns`, `GET/PATCH /api/campaigns/{id}`, `POST /api/campaigns/validate`, `POST /api/campaigns/{id}/status`. Calendar filters use `start_date` and `end_date` on `GET /api/campaigns`.
- **Rules:** creation starts in Draft; edits are allowed only in Draft; end date cannot precede start date; referenced segments/offers must exist; attached offers must be Active; duplicate name/start date is rejected; status transitions follow the lifecycle graph; each transition is recorded.
- **Acceptance:** campaign drafts survive API restarts, API validation lists audience/consent/offer/duplicate/budget checks, status transitions reject invalid edges, and the calendar displays records returned for its selected month.

## Customer 360

- **Purpose:** show a masked customer profile, current subscription, usage, value, consent, risk and interaction history.
- **User stories:** an operator can search by name or customer ID, open a profile, review its history and record an opt-out or consent preference change.
- **Data:** customer type/status, masked identifier, segment, plan, tenure, recharge/revenue history, usage, lifetime value, campaign engagement, preferred channel, churn risk and consent.
- **APIs:** `GET /api/customers?q=&segment=`, `GET /api/customers/{id}`, `PATCH /api/customers/{id}/consent`.
- **Rules:** synthetic identifiers stay masked; consent changes are persisted with a reason and timestamp; no message is sent from this screen.
- **Acceptance:** search returns matching API profiles; profile detail shows history and usage; consent changes remain after reload.

## Audience and Segments

- **Purpose:** save reusable static or dynamic audiences using nested AND/OR customer rules.
- **User stories:** an analyst can add conditions, choose the group combinator, estimate against sample records, save a segment and edit its rules.
- **Data:** segment name/description/mode, recursive rule groups, sample count, sample customer IDs, update date and count basis.
- **APIs:** `GET/POST /api/segments`, `GET/PUT /api/segments/{id}`, `POST /api/segments/estimate`.
- **Rules:** only allowlisted customer fields and operators are accepted; comparisons do not evaluate arbitrary expressions; a dynamic segment refreshes against the current local customer sample; static membership is stored as a snapshot; the UI labels seed estimates separately from computed sample counts.
- **Acceptance:** invalid fields/operators are rejected by validation; estimates return count and sample IDs; saving/editing persists the definition; dynamic previews refresh after customer changes.

## Offer Management

- **Purpose:** define reusable products/promotions and control their status before campaign use.
- **User stories:** a manager can create a draft offer, set product/price/validity/eligibility/channel restrictions/limits, request approval, approve it, and inspect its version/status history.
- **Data:** offer attributes, status, version, update date, and approval history.
- **APIs:** `GET/POST /api/offers`, `GET/PATCH /api/offers/{id}`, `POST /api/offers/{id}/status`.
- **Rules:** offers start Draft; only Draft offers can be edited; activation follows Draft → Pending Approval → Active; invalid dates and non-positive validity are rejected; campaigns may only reference Active offers.
- **Acceptance:** created offers survive restart; updates increment version; transitions append actor/reason/time; campaign validation rejects inactive offers.

## Scenario Studio

- **Purpose:** create reusable campaign plans from a saved audience, an active offer, a channel and a message template.
- **User stories:** a campaign manager can create or import a scenario definition, preview who would qualify, see masked subscriber identifiers and personalized message examples, and save an idempotent simulation run.
- **Data:** scenario definition/version, segment and offer references, selected channel, schedule, template, consent-filtered preview counts and simulation runs.
- **APIs:** `GET/POST /api/scenarios`, `POST /api/scenarios/import`, `GET/PUT /api/scenarios/{id}`, `POST /api/scenarios/{id}/preview`, `POST /api/scenarios/{id}/simulate`, `GET /api/scenarios/{id}/runs`.
- **Rules:** a referenced segment must exist; an attached offer must be Active; only consented customers enter the eligible preview; sample subscriber numbers remain masked; repeated idempotency keys do not create duplicate runs; simulation sends zero messages.
- **Acceptance:** imported JSON scenario definitions are validated and saved as drafts; previews expose target, eligible and consent-excluded counts plus a masked customer sample; simulation history persists after restart.

## Data boundary

SQLite persistence is configured for local Phase 2 development. It is not a tenant-isolated production database. Consent editing currently records a development operator reason; production authentication, scoped permissions and tamper-resistant audit trails remain enterprise-hardening work.
