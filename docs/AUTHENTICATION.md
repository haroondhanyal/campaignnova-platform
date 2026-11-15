# Sign-in, profiles, and department access

## Local setup

1. Start the backend and web app using the repository instructions.
2. Open `/signup` and choose **Super Admin** to initialize an existing workspace that has no accounts yet. Production also requires `CAMPAIGNNOVA_BOOTSTRAP_TOKEN`. This creates the first Super Admin and signs them in; it does not create a company workspace.
3. A signed-in Super Admin can create a company workspace and its first Super Admin from `/user-roles`. They can also provision accounts directly or approve pending User signup requests.
4. Users choose their company by name/logo on `/login`. Admin-created accounts must change their temporary password on first sign-in. The optional “Remember this device” setting keeps the HTTP-only session active for 30 days instead of 12 hours; it never stores the password.

User self-signups to existing workspaces remain pending until an administrator approves and assigns a role. Users cannot join an unclaimed workspace before its first Super Admin setup. Passwords are stored as salted PBKDF2-SHA256 hashes. Successful sign-in issues a 12-hour HTTP-only, SameSite=Lax session cookie. Logout, password change, password reset, and account disable revoke existing sessions.

## Account screens and API

- `/signup`: choose User account, Company account, or Super Admin. Users request to join an existing workspace. Initial Super Admin setup is limited to an unclaimed workspace. Company accounts/workspaces are created only by a signed-in Super Admin from `/user-roles`.
- `/login`: searchable company workspace picker with local logo, email, password, and optional 30-day remembered session.
- `/forgot-password` and `/reset-password`: company workspace code plus one-time, 30-minute reset links.
- `/profile`: profile photo and phone update, plus password change. Email is the immutable sign-in ID.
- `/user-roles`: Super Admin and Organization Admin account, department, role, module assignment, and approval panel.
- `/settings`: company name, logo, company-enabled modules, and workspace preferences. Company branding is shown on sign-in and in the signed-in workspace.
- `/feature-access`: browse the module catalog, request an unassigned feature, review requests, and customize department-level access.
- `/api/auth/setup-status`, `/signup`, `/login`, `/logout`, `/me`, `/me/avatar`, `/password`, `/forgot-password`, and `/reset-password` implement account flows.
- `/api/admin/users` and `/api/admin/roles` require administrator authentication. Domain APIs also check the signed-in account's department and read-only role.

Profile photos accept PNG, JPEG, or WebP images up to 15 MB. Company logos accept the same types up to 2 MB. Images are signature-checked and stored in the local SQLite JSON store. Company logos are served as public branding assets; profile photos remain access-controlled.

Phone inputs use international country calling codes, numeric-only national-number fields, localized examples, and country-specific possible-length checks. The API also validates digits and the national number length for the commonly used country codes.

## Department and role options

Every company workspace offers reusable department options for Administration, Marketing, Commercial, CVM, Segments, Customer Care, Sales, Customer Success, Product & Services, Retail Sales, Digital Services, Business Development, Business Operations, Operations, Campaign Operations, Data & Analytics, Engineering, Technology & IT, Finance, Human Resources, People & Organization, Carrier & International Wholesale, and Legal & Regulatory. Each workspace assigns its own users to departments and roles. Each signed-in session scopes campaign, customer, segment, offer, scenario, governance, and settings records to its company.

Roles include Super Admin, Organization Admin, Admin, Department Manager, Campaign Manager, CVM Manager, Segment Analyst, Customer Care Agent, Commercial Analyst, Campaign Agent, Agent, Approver, Data Analyst, Integration Admin, and Viewer. A new company workspace begins with core modules. Its Super Admin can brand the company workspace and enable optional modules. Department Managers can manage only their own department’s allocation from the company-enabled modules. Employees can request any catalog feature; the Super Admin can approve it, which enables the feature for that company if needed and grants it to the requesting department and account. Department Managers may approve requests for their own department only after the company has enabled the feature. Requests and access changes are tenant-scoped and audited. API and navigation scopes follow the company-enabled set, department policy, and any account-level module assignment. Read-only roles cannot submit changes outside the feature-request workflow. An unclaimed existing workspace can receive its initial Super Admin through the dedicated setup flow. Once claimed, further Super Admin accounts must be provisioned by an existing Super Admin.

## Password reset email

When SMTP is configured, the API emails reset links. Otherwise, development mode returns a local development link on the forgot-password screen. No reset URL is returned in production.

Set these backend environment variables:

```dotenv
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=campaignnova@example.com
SMTP_PASSWORD=replace-with-a-secret
SMTP_FROM_EMAIL=campaignnova@example.com
SMTP_STARTTLS=true
CAMPAIGNNOVA_PUBLIC_WEB_URL=https://campaigns.example.com
CAMPAIGNNOVA_WEB_ORIGINS=https://campaigns.example.com
CAMPAIGNNOVA_SECURE_COOKIES=true
```

For first-time production Super Admin setup, set `CAMPAIGNNOVA_BOOTSTRAP_TOKEN` and enter it in the Super Admin signup flow. Local development does not require this token.

## Deployment boundary

This is an application-level login and department access system, not a configured corporate identity deployment. Before real subscriber or employee use, configure TLS, approved identity/email policies, account verification, SSO/MFA if required, a production database with backups, distributed login/reset rate limiting, audit retention, and monitored mail delivery. The app uses only CampaignNova branding and does not depend on any single carrier’s logo or employee identity system.
