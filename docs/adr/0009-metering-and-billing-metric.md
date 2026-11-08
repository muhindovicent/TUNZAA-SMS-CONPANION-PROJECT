# ADR 0009: Metering by active women and SMS segments

- Status: Accepted
- Date: 2026-10-31

## Context

Buyers ask for cost per woman and per message. Billing is out of scope, but the metering hooks
must match the commercial model from the start and support per-tenant spend caps.

## Decision

- Meter per tenant per calendar month: active women, messages sent and SMS segments sent.
- Active women are counted as distinct women with an active pregnancy record during the
  month, with the exact counting rule documented and tested.
- Segments come from the shared GSM-7/UCS-2 counter used at template approval and send time.
- Expose usage as reports and a machine-readable export. Do not implement invoicing, payment
  collection or tax logic in this platform.
- Enforce per-tenant daily SMS spend caps and low-balance alerts.
- Pricing figures and the final commercial metric remain a buyer negotiation; the metering
  hooks support per-woman, per-message and per-facility reporting without schema changes.

## Consequences

- `usage_records` and cost tracking land in M5 with delivery.
- Report suppression rules still apply; usage exports contain no patient identifiers.
- Cost anomalies are visible to tenant admins and platform owners without exposing patient
  data.
