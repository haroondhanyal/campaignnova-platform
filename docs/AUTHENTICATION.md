# Sign-in, profiles, and department access

## Local setup

1. Start the backend and web app using the repository instructions.
2. Open `/signup`, enter the company name, and create its workspace. The first account for that company becomes its Super Admin and is signed in automatically. The workspace code is the company name in lowercase with spaces replaced by hyphens.
3. In the admin panel, approve team signup requests or create employee accounts with a department, role, phone, and temporary password.
4. Employees sign in at `/login` using the company workspace code, email, and password. Admin-created accounts must change their temporary password on first sign-in. The optional “Remember this device” setting keeps the HTTP-only session active for 30 days instead of 12 hours; it never stores the password. Password fields use browser password-manager autocomplete, so Chrome may offer to save credentials to Google Password Manager.

Later self-signups remain pending until an administrator assigns a role and enables the account. Passwords are stored as salted PBKDF2-SHA256 hashes. Successful sign-in issues a 12-hour HTTP-only, SameSite=Lax session cookie. Logout, password change, password reset, and account disable revoke existing sessions.

## Account screens and API

- `/signup`: company name, account name, work email, country calling code, phone number, department, profile image, and password. The first account becomes that workspace Super Admin; repeat signup joins that company as a pending request.
- `/login`: workspace code, email, password, and optional 30-day remembered session. Entering a valid workspace code previews that company's name and logo.
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

Roles include Super Admin, Organization Admin, Admin, Department Manager, Campaign Manager, CVM Manager, Segment Analyst, Customer Care Agent, Commercial Analyst, Campaign Agent, Agent, Approver, Data Analyst, Integration Admin, and Viewer. A new company workspace begins with core modules. Its Super Admin can brand the company workspace and enable optional modules. Department Managers can manage only their own department’s allocation from the company-enabled modules. Employees can request any catalog feature; the Super Admin can approve it, which enables the feature for that company if needed and grants it to the requesting department and account. Department Managers may approve requests for their own department only after the company has enabled the feature. Requests and access changes are tenant-scoped and audited. API and navigation scopes follow the company-enabled set, department policy, and any account-level module assignment. Read-only roles cannot submit changes outside the feature-request workflow. The first account in each company is its public self-signup path to Super Admin.

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

For first-time production bootstrap, set `CAMPAIGNNOVA_BOOTSTRAP_TOKEN` to a one-time secret and enter it on the initial signup form. The local development defaults do not require this token.

## Deployment boundary

This is an application-level login and department access system, not a configured corporate identity deployment. Before real subscriber or employee use, configure TLS, approved identity/email policies, account verification, SSO/MFA if required, a production database with backups, distributed login/reset rate limiting, audit retention, and monitored mail delivery. The app uses only CampaignNova branding and does not depend on any single carrier’s logo or employee identity system.
