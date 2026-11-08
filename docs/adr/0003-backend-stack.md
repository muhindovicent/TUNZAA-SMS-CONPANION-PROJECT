# ADR 0003: Backend stack and dependency discipline

- Status: Accepted
- Date: 2026-10-31

## Context

Government and NGO buyers audit dependencies. The stack must be boring, well maintained,
licence-clear and container friendly. The application is transactional and data-sensitive,
not compute-heavy.

## Decision

- Python 3.12, Flask 3, SQLAlchemy 2, Alembic, Pydantic v2, gunicorn.
- PostgreSQL 16 with constraints, enums, CHECKs and foreign keys in the schema.
- Argon2id for passwords, `cryptography` for field and envelope encryption, `structlog` for
  structured logs and OpenTelemetry for traces and metrics.
- `psycopg` 3 as the PostgreSQL driver. SQLite is confined to developer laptops and fast unit
  tests; integration and RLS tests run on PostgreSQL.
- Dependencies are pinned, reviewed for licence and maintenance, scanned with `pip-audit`,
  `bandit`, Trivy and recorded in an SBOM per release.
- Each new dependency needs a short justification in the pull request or an ADR.

## Consequences

- One Python package, one dependency set and one image for web and worker.
- No ORM-only domain logic: constraints remain in the database.
- Python 3.12 is the supported runtime even if newer interpreters are available locally.
- OIDC, DHIS2 and FHIR adapters must not introduce unvetted crypto or XML stacks; each is
  reviewed before adoption.
