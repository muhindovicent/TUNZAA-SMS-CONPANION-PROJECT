# Tunza decisions log

This log records decisions taken where the brief was silent or where a buyer choice was
required. Architecture decisions have full ADRs under `docs/adr/`.

| ID | Date | Decision | Status | Source |
| --- | --- | --- | --- | --- |
| D-001 | 2026-10-31 | Build a modular monolith, not microservices | Accepted | ADR 0001 |
| D-002 | 2026-10-31 | Isolate tenants with `org_id` plus PostgreSQL RLS | Accepted | ADR 0002 |
| D-003 | 2026-10-31 | Use Python 3.12, Flask 3, SQLAlchemy 2, Alembic, Pydantic v2 and PostgreSQL 16 | Accepted | ADR 0003 |
| D-004 | 2026-10-31 | Use server-side sessions, Argon2id, mandatory MFA and OIDC SSO in the first release | Accepted | ADR 0004 |
| D-005 | 2026-10-31 | Use a provider-agnostic SMS gateway with console and Africa's Talking adapters first | Accepted | ADR 0005 |
| D-006 | 2026-10-31 | Use vanilla HTML, CSS and JavaScript with no framework and no build step | Accepted | ADR 0006 |
| D-007 | 2026-10-31 | Target hosted multi-tenant for the first release, keeping dedicated and customer-hosted packaging ready | Accepted | ADR 0007 |
| D-008 | 2026-10-31 | Use AES-256-GCM field encryption, HMAC phone hashes and per-tenant envelope keys | Accepted | ADR 0008 |
| D-009 | 2026-10-31 | Meter active women, messages and SMS segments per tenant per month; billing is out of scope | Accepted | ADR 0009 |
| D-010 | 2026-10-31 | Allow VHTs and facility staff to enrol women, with facility scope limited to home facility plus consent | Accepted | ADR 0010 |
| D-011 | 2026-10-31 | Include OIDC SSO in the first release; defer DHIS2 and FHIR until a named buyer requires them | Accepted | ADR 0011 |
| D-012 | 2026-10-31 | Default alert chain T+0 VHT, T+30 facility on-call plus supervisor, T+60 admin SLA breach; confirm per tenant in writing | Accepted default | Brief section 7 |
| D-013 | 2026-10-31 | Use synthetic data only; seed commands and console OTP refuse to run when `APP_ENV=production` | Accepted | Brief sections 0 and 12 |
| D-014 | 2026-10-31 | Do not claim ISO 27001, SOC 2 or similar certifications; build to be audit-ready and say exactly that | Accepted | Brief section 2 |
| D-015 | 2026-10-31 | Default timezone Africa/Kampala; EDD from LMP plus 280 days, ultrasound override stored with `edd_source` | Accepted | Brief section 7 |

## Open decisions requiring the customer or legal input

| ID | Question | Owner | Needed by |
| --- | --- | --- | --- |
| O-001 | Where may data legally and contractually reside for the first buyer? | Buyer, Zest, legal counsel | Before production onboarding |
| O-002 | Who is the first named clinical reviewer and DPO for each tenant? | Tenant signatory | Before go-live gate 1 and 3 |
| O-003 | What are the exact alert SLAs and escalation contacts per tenant? | Tenant, facility, supervisor | Before go-live gate 6 |
| O-004 | What legal period applies to breach notification? | Legal counsel | Before production |
| O-005 | Which OIDC identity provider and mapping rules will the first buyer use? | Buyer, Zest | Before M1 SSO tests |
| O-006 | Do Luganda danger keywords and templates pass native-speaker and reviewer sign-off? | Clinical reviewer, native speaker | Before go-live gate 1 |
| O-007 | Is the pilot limited to one district and a small consented group? | Tenant, Zest | Before go-live gate 9 |
| O-008 | Final pricing metric and figures for the first contract | Zest commercial | Before first invoice |
