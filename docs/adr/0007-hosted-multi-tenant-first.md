# ADR 0007: Hosted multi-tenant deployment for the first release

- Status: Accepted
- Date: 2026-10-31

## Context

Tunza must ultimately support three deployment models: Zest-hosted multi-tenant, dedicated
single-tenant and customer-hosted containers. Building three operating models at once would
dilute the security and clinical work. The first buyer decision was required before schema and
operations were fixed.

## Decision

Target Zest-hosted multi-tenant for the first release. Keep dedicated and customer-hosted
deployments as configuration and container packaging concerns, not forks:

- tenant-aware schema with `org_id` and RLS from day one;
- per-tenant settings, keys, sender IDs, quotas and languages;
- no hard dependency on a single cloud provider;
- all services runnable from container images with environment-based configuration.

## Consequences

- Shared infrastructure requires strict tenant isolation, per-tenant encryption keys,
  metering and support-access controls.
- The data-residency location remains a flagged decision with legal and contractual input.
- Dedicated and customer-hosted deployments are documented as supported packaging, but are
  not claimed as delivered until a buyer requires and tests them.
- Tenant onboarding, suspension, export and offboarding are first-class lifecycle features.
