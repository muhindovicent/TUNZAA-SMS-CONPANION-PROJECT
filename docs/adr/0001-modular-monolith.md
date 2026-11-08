# ADR 0001: Modular monolith over microservices

- Status: Accepted
- Date: 2026-10-31
- Owners: Zest Technologies engineering

## Context

Tunza is a multi-tenant maternal-health platform that must be secure, auditable, easy to
operate and easy to hand over to a government or NGO buyer. The team is small, the domain is
tightly coupled (patients, consent, scheduling, messaging, alerts, audit) and every service
boundary would add deployment, tracing and failure-mode cost.

## Decision

Build one deployable application with strict internal module boundaries. The same container
image runs the Flask web process and the background worker. Each module owns its tables and
is called only through a service interface. PostgreSQL remains the single transactional
store. Modules may be extracted later only when a measured need exists.

## Consequences

- Simpler local development, one migration history, one deploy, one set of traces.
- Cross-module transactions stay correct without distributed-saga machinery.
- Boundary discipline must be enforced by review, import rules and tests rather than network
  isolation.
- Scaling is by replicas of web and worker, not by independent service scaling.
- No claim of microservice maturity in procurement material.
