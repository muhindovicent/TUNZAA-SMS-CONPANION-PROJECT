# Tunza threat model

Status: M0 initial model. Updated every milestone.
Method: STRIDE over the container and data-flow views in `docs/architecture.md`.

## 1. Scope and assets

In scope: the web application, worker, PostgreSQL, object storage, SMS provider callbacks,
role experiences, audit pipeline, backups and deployment tooling.

Assets, in order of sensitivity:

1. Pregnancy and clinical data: names, phone numbers, LMP, EDD, danger signs, guardians,
   consent evidence.
2. Authentication material: password hashes, session IDs, invitation tokens, OTPs, TOTP
   secrets, WebAuthn credentials, OIDC tokens.
3. Tenant configuration and provider credentials.
4. Audit trail, go-live gate evidence and approval records.
5. Availability of reminders and danger-sign alerts.
6. Encryption keys and backup material.

## 2. Actors and trust boundaries

Actors: pregnant woman, guardian, VHT, supervisor, facility staff, clinical reviewer, tenant
admin, DPO, partner viewer, platform owner, platform support, SMS provider, integration
consumer, backup operator, attacker.

Trust boundaries:

- internet to edge;
- edge to web;
- web to PostgreSQL and object storage;
- worker to SMS provider;
- SMS provider to inbound webhook;
- application roles to each other;
- application to audit archive;
- application to KMS or secrets store;
- platform support to tenant data.

## 3. STRIDE summary

| Threat | Example | Primary mitigations | Milestone |
| --- | --- | --- | --- |
| Spoofing | Stolen session or forged OIDC identity | Server-side sessions, rotation, HttpOnly/Secure cookie, CSRF, MFA, issuer/audience validation, no privileged auto-provisioning | M1 |
| Tampering | Editing audit rows or replayed callbacks | Append-only triggers, hash chain, off-box shipping, idempotent callback handling, HMAC outbound webhooks | M2, M6 |
| Repudiation | Reviewer denies approving a template | Signed approvals, audit rows with actor, role, object and time | M2, M4 |
| Information disclosure | Tenant A reads tenant B; log leaks a phone number | `org_id` + RLS, SQL scope checks, 404 outside scope, field encryption, log redaction, masked phone reveal | M2, M3 |
| Denial of service | Login or webhook flooding; SMS provider outage | Rate limits, request size limits, edge limits, failover, retry with backoff, spend caps | M5, M6, M10 |
| Elevation of privilege | Admin approves clinical content; self-granted role | Server-side permission map, separation of duties, two-person approval, route-map test, role change ends sessions | M1, M2 |
| Supply chain | Malicious dependency or image | Pinned dependencies, pip-audit, Trivy, SBOM, signed images, gitleaks | M0, M10 |
| Insider misuse | Platform support reads patient data | No default patient access, time-limited tenant-approved diagnostics-only support, full audit, no impersonation | M2 |
| Key compromise | Stolen field key or backup | Envelope encryption, KMS/secrets store, key IDs for rotation, encrypted backups, restore drills | M3, M9 |
| Shared-phone disclosure | Another person replies from the woman's phone | Never reveal pregnancy information to an unverified replier; re-verification flow | M6 |

## 4. High-priority abuse cases

### Cross-tenant access

- Attempt API, direct SQL under the app role, and RLS bypass. Expected: denied, 404 for
  out-of-scope and an audit entry.
- Background jobs must set tenant context per unit of work; a missing context must fail
  closed, not read all tenants.

### Privilege escalation and separation of duties

- No one grants authority equal to or above their own and no one approves their own request.
- A DPO must not also be an org admin; warn if the same person holds both.
- Admins and platform roles cannot approve clinical content. The clinical reviewer cannot
  manage users or configuration.
- Partner viewer access expires after 6 months unless renewed.

### Audit tampering

- Database triggers refuse `UPDATE` and `DELETE` on `audit_log`.
- Rows are hash-chained and shipped continuously to an object-lock bucket or external syslog.
- A database administrator cannot silently rewrite history.

### SMS callback abuse

- Do not assume callbacks are signed. Use HTTPS, an unguessable path token, published IP
  allowlists, strict payload validation, rate limits and idempotency.
- Handle duplicate and out-of-order callbacks without double-sending or corrupting state.

### Personal data in logs and browsers

- Never log phone numbers, names, message text tied to a person, passwords, tokens or OTPs.
- No identifiable data in localStorage or IndexedDB. Form drafts stay in page memory only.
- The service worker never caches API responses or personal data.

### Go-live bypass

- A tenant with any open `go_live_gates` row cannot send live messages. This is enforced in
  the planner and again in the worker.

## 5. Residual risks and open items

- Hosting location and legal basis for cross-border processing are not yet decided.
- Shared-phone households and changed numbers need field validation with real VHTs.
- Luganda danger keywords require a native speaker and clinical reviewer confirmation.
- Alert SLAs and escalation contacts must be agreed in writing per tenant.
- Provider callback formats must be re-checked against current documentation before M6.
- Independent penetration testing has not been performed; no certification is claimed.
- Breach notification deadlines are not hard-coded; legal counsel must confirm the period.

## 6. Review log

| Date | Milestone | Change |
| --- | --- | --- |
| 2026-10-31 | M0 | Initial STRIDE model, trust boundaries and abuse cases |
