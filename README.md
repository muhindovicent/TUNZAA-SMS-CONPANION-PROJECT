# Tunza

Tunza is an SMS companion for pregnant women plus a facility and community-health-worker
management platform, aligned to the WHO and Uganda MOH 8-contact antenatal care schedule.

This repository is at **M0 Foundations**, ready for milestone review. It is not cleared for real
patients. It contains no real patient data and must only be used with synthetic data.

## Safety rules

- Never use real patient data in development, tests, demos, screenshots or logs.
- Never log phone numbers, names, message text tied to a person, passwords, tokens or OTPs.
- Never weaken a security rule to make a test pass.
- No certification (ISO 27001, SOC 2 or similar) is claimed. The design is built to be
  audit-ready and says exactly that.

## Stack

- Python 3.12, Flask 3, SQLAlchemy 2, Alembic, Pydantic v2, gunicorn, PostgreSQL 16.
- Vanilla HTML, CSS and JavaScript with no framework and no production build step.
- JSDoc types checked with `tsc --checkJs` as a dev-time check only.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
python -m flask --app tunza.wsgi:app run --debug
```

On Linux or macOS use `source .venv/bin/activate` and `cp .env.example .env`.

The development default uses SQLite. To use PostgreSQL 16 locally:

```powershell
docker compose up -d db
$env:DATABASE_URL = "postgresql+psycopg://tunza:tunza@localhost:5432/tunza"
alembic upgrade head
```

Health endpoints: `/healthz` and `/readyz`.

## Tests and checks

```powershell
pytest
ruff check .
mypy src
bandit -c pyproject.toml -r src -q
pip-audit
npm ci
npm run typecheck
```

CI runs the test and migration checks on PostgreSQL 16, plus linting, type checks, dependency
and secret scanning and front-end type checking.

To run the PostgreSQL-only checks locally, point `TEST_DATABASE_URL` at a disposable database:

```powershell
$env:TEST_DATABASE_URL = "postgresql+psycopg://tunza:tunza@localhost:5432/tunza_test"
pytest
```

## Layout

```text
src/tunza/
  app.py                 Flask application factory
  config.py              environment settings and production safety guards
  logging.py             structured logging with PII redaction
  db/                    engine, models, RLS helpers
  security/              phone normalisation, masking and HMAC hashing
  messaging/             segment counting and provider gateways
  modules/               strict domain module boundaries
  web/                   health endpoints, security headers, static assets
migrations/              Alembic migrations
docs/                    architecture, ADRs and threat model
tests/                   unit, migration and readiness tests
```

## Documentation

- `docs/architecture.md` — containers, modules, data flows and capacity targets.
- `docs/threat-model.md` — STRIDE model and abuse cases.
- `docs/adr/` — architecture decision records.
- `DECISIONS.md` — decisions and open customer/legal questions.
- `RUNBOOK.md` — incident and recovery runbooks.

## Milestone status

M0 Foundations is ready for review. Later milestones are listed in `docs/architecture.md` and
in the master product brief. Each milestone stops for review after its tests pass.
