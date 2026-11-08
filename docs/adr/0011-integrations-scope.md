# ADR 0011: OIDC in first release; DHIS2 and FHIR deferred

- Status: Accepted
- Date: 2026-10-31

## Context

Interoperability work is buyer-driven and can consume a large share of delivery effort before
a named customer needs it. A buyer has explicitly asked for single sign-on. No first-release
buyer has asked for DHIS2 push or a FHIR facade.

## Decision

- Include OIDC SSO in the first release (see ADR 0004).
- Defer DHIS2 aggregate push and the FHIR R4 facade until a named buyer requires them.
- Keep the design ready: de-identified aggregate queries, configurable mapping points,
  per-tenant API keys, HMAC-signed outbound webhooks and a read-only integration facade seam.
- Confirm current Uganda MOH DHIS2 requirements before any DHIS2 implementation.

## Consequences

- M8 reporting and integrations deliver reports, exports, outbound webhooks and API keys.
- DHIS2 and FHIR remain feature-flagged and unbuilt; no procurement claim says otherwise.
- OIDC configuration is tenant-scoped and does not create a hard dependency on one identity
  provider.
