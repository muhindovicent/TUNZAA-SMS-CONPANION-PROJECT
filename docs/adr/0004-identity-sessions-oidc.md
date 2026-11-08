# ADR 0004: Identity, sessions, MFA and OIDC SSO

- Status: Accepted
- Date: 2026-10-31
- Supersedes: none

## Context

Roles range from platform owner to village health team member. Accounts are individual, never
shared. Privileged actions must be resistant to phishing and session theft. A named buyer has
asked for single sign-on in the first release.

## Decision

- Accounts are created only through approved invitations. No self-registration. Invitation
  tokens are single-use, stored only as hashes, expire after 72 hours and are never logged.
- Users choose their own password. Passwords are at least 12 characters, checked against a
  common-password list and hashed with Argon2id. No administrator can see or set a password.
- Authentication responses are identical for unknown users and wrong passwords. Five failures
  lock the account for 15 minutes and notify the owner. Rate limits apply by account and IP.
- Server-side sessions hold a random identifier; cookies are HttpOnly, Secure and
  SameSite=Lax. Sessions rotate on login and role change. CSRF tokens guard every
  state-changing request. Nothing sensitive is stored in localStorage.
- Second factor is mandatory for every role except `partner_viewer`. SMS is the baseline;
  TOTP and WebAuthn are supported and recommended. The development console OTP path is
  impossible when `APP_ENV=production`.
- OIDC SSO is in the first release. It maps verified issuer identities to pre-existing
  accounts and roles. It does not auto-provision privileged roles. Local password and MFA
  remain available as a governed fallback.
- A vetted OIDC client library will be selected in M1 after licence and maintenance review.
  No home-grown token validation will be written.

## Consequences

- Identity tables and session handling land in M1 before any role page exists.
- SSO configuration is per tenant through tenant settings and environment secrets.
- Role or scope changes terminate the user's sessions.
- OIDC integration tests use a local mock identity provider, never a production tenant.
- No certification claim follows from using OIDC.
