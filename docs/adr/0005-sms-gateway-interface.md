# ADR 0005: Provider-agnostic SMS gateway interface

- Status: Accepted
- Date: 2026-10-31

## Context

SMS is the clinical delivery channel. Providers differ in authentication, status codes,
callback formats and failure behaviour. A tenant may need more than one provider, and
government buyers may mandate a local aggregator.

## Decision

- Define a narrow `SmsGateway` contract: `send_message`, `parse_delivery_report` and
  `parse_inbound`, with normalised result and status types.
- Ship a console gateway for development and tests, and an Africa's Talking adapter first.
- Support more than one provider per tenant with explicit failover. Provider credentials are
  per-tenant, encrypted at rest and never logged.
- Callbacks are treated as untrusted. Use HTTPS only, an unguessable path token, published IP
  allowlists where available, strict payload validation, rate limits and idempotent handling
  of duplicate and out-of-order callbacks. Do not assume callbacks are signed.
- Message text comes only from approved, versioned templates. Segment counting is computed
  before approval and again at send time.
- Callback parsing is re-validated against current provider documentation in M6.

## Consequences

- The messaging module depends on the interface, not on a provider SDK.
- Provider-specific quirks stay inside adapters and their tests.
- A provider outage can fail over without changing scheduling or clinical logic.
- No phone number, message body or OTP is written to logs by any adapter.
