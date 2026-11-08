# ADR 0002: Tenant isolation with org_id and PostgreSQL RLS

- Status: Accepted
- Date: 2026-10-31

## Context

A cross-tenant leak of pregnancy data would be a legal and commercial failure. Application
permission checks alone are not sufficient defence in depth. The platform must support hosted
multi-tenant, dedicated and customer-hosted deployments from the same schema.

## Decision

- `organisations` is the tenant root and every business table carries `org_id NOT NULL`.
- PostgreSQL row-level security is enabled on tenant-scoped tables and keyed on `org_id`.
- The application sets `app.org_id` per transaction with `SET LOCAL` semantics through
  `set_config('app.org_id', ..., true)`. No connection pooling value persists across requests.
- The runtime database role has no `BYPASSRLS`; migrations run under a separate role.
- RLS is defence in depth. Application permission and scope checks remain mandatory, and
  out-of-scope reads return 404.
- SQLite is allowed for local unit tests only; RLS tests run against PostgreSQL in CI.

## Consequences

- Every query path must run inside a transaction with tenant context set.
- Background jobs must set tenant context explicitly per tenant unit of work.
- Tenancy tests must attempt both API access and direct SQL under the app role.
- Platform support access is time-limited, tenant-approved, diagnostics-only and audited.
- No impersonation feature will be built.
