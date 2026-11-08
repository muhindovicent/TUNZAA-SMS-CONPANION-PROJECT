# Tunza runbook

Status: M0 skeleton. Steps are completed and tested in M9 and M11. Until then, treat any
production use as unsupported.

Operating rules for every incident:

- Never paste phone numbers, names, message text, passwords, tokens or OTPs into tickets,
  chat or logs. Use the masked application views and audit references.
- Record times in Africa/Kampala and UTC.
- Preserve evidence before changing state. Do not edit or delete audit rows.
- Escalate irreversible actions (key destruction, tenant deletion, failover with data loss
  risk) to the named incident lead and the tenant.

## 1. SMS provider outage

Detect: delivery rate falls, provider errors rise, outbox depth grows, provider balance or
status page alerts.

1. Confirm scope: one tenant, one provider or all tenants.
2. Check the console gateway is not active in production.
3. Fail over to the tenant's secondary provider if configured and approved.
4. Pause non-emergency planning if the backlog would breach quiet hours or spend caps.
5. Keep danger-sign inbound and alerts running; these take priority.
6. Notify the tenant admin and record the incident timeline.
7. Reconcile delivery reports idempotently after recovery.

## 2. Database failover

Detect: `/readyz` database check fails, connection errors, replication lag alert.

1. Confirm the primary is unreachable and the failure is not application-only.
2. Follow the approved failover procedure for the hosting model.
3. Verify RLS roles, extensions, migrations and audit triggers on the new primary.
4. Run integrity checks and confirm the audit chain.
5. Restart workers only after the database is writable and heartbeats are fresh.
6. Record RPO/RTO actuals and any lost messages.

## 3. Outbox stall

Detect: oldest unsent message metric, outbox depth alert, missing worker heartbeat.

1. Check worker heartbeat and dead-man's switch.
2. Inspect leased rows without exposing message bodies.
3. Confirm provider credentials, balance and rate limits.
4. Release expired leases through the documented tool, never by manual status edits.
5. Confirm no duplicate sends after recovery.
6. Escalate to the tenant if clinical reminders are delayed.

## 4. Alert SLA breach

Detect: oldest unacknowledged alert, SLA timer expiry.

1. Confirm the alert was raised and the VHT was notified.
2. Contact the facility on-call and supervisor through the agreed chain.
3. Record the breach and the reason.
4. If the alert chain itself failed, treat it as a severity-1 incident.
5. Review the case with the clinical reviewer and tenant admin.

## 5. Leaked credential

Detect: gitleaks, provider notice, unexpected usage, suspicious login.

1. Revoke the credential and rotate it through the secrets manager.
2. Terminate affected sessions and revoke API keys.
3. Review audit and authentication events for use of the credential.
4. If patient data may have been accessed, start the breach procedure.
5. Record the root cause and add a preventive control.

## 6. Breach response

1. Contain and preserve evidence.
2. Assess categories and volume of data, and the affected tenants and women.
3. Notify the incident lead, DPO and tenant signatory.
4. Notify the regulator within the period confirmed by legal counsel; do not assume a
   deadline.
5. Communicate in plain language without exposing other people's data.
6. Complete a post-incident review and update this threat model.

## 7. Tenant offboarding

1. Confirm the tenant signatory request and retention obligations.
2. Produce the full export in open formats (CSV and JSON).
3. Verify the export integrity with the tenant.
4. After the retention period, destroy the wrapped tenant data key to crypto-shred.
5. Retain only the minimum legally required audit and billing records.
6. Record the offboarding evidence and remove access.

## 8. Key rotation

1. Create the new key with a new key ID.
2. Re-wrap tenant data keys under the new master key.
3. Keep old keys available for the documented overlap window only.
4. Re-encrypt field values in the background with idempotent checkpoints.
5. Verify read paths and key-ID handling.
6. Destroy old keys after the overlap window and record the event.

## 9. Restore drill

1. Restore the latest full backup plus WAL to a clean environment.
2. Run integrity checks, RLS tests and the audit-chain verifier.
3. Confirm RPO and RTO actuals against the target.
4. Record results and any gaps.
5. Do not point the restored database at production traffic.

## 10. Dead-man's switch

Detect: scheduler or worker heartbeat older than two intervals, external `/readyz` failure.

1. Confirm the process is not running or is stuck.
2. Check database, provider and host health.
3. Restart the process and verify a fresh heartbeat.
4. Inspect for missed planner runs, expired leases and unsent messages.
5. Page the on-call person by SMS and email as configured.
