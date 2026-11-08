# ADR 0008: Field encryption, HMAC lookup and per-tenant keys

- Status: Accepted
- Date: 2026-10-31

## Context

Pregnancy is special personal data under Uganda's Data Protection and Privacy Act, 2019.
Names, phone numbers and guardian details are the highest-risk fields. Lookups by phone must
remain possible without storing plaintext, and tenant offboarding must be able to render data
unrecoverable.

## Decision

- TLS 1.2 or higher; TLS 1.3 preferred.
- Encrypt names, phone numbers and guardian details at field level with AES-256-GCM. Every
  value carries a key identifier so keys can rotate.
- Store an HMAC-SHA-256 `phone_hash` for equality lookups. The HMAC key is separate from the
  field-encryption keys.
- Use envelope encryption per tenant: a tenant data key is wrapped by a master key held in a
  KMS or secrets store. Destroying the wrapped data key crypto-shreds that tenant's data after
  the retention period.
- Encrypt disks and backups. Secrets come only from the environment or a secrets manager; a
  committed secret fails CI.
- Do not claim ISO 27001, SOC 2 or any similar certification. Build to be ready and state
  exactly that.

## Consequences

- Encryption and key rotation are implemented in M3 before patient records exist.
- Queries that need exact phone matching use `phone_hash`, never ciphertext.
- Key rotation, restore and tenant offboarding runbooks must be tested.
- Support staff and platform roles cannot read patient fields by default.
