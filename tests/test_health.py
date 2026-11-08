from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import text

from tunza.db.engine import Database


def test_healthz_returns_ok(client: FlaskClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_security_headers_are_present(client: FlaskClient) -> None:
    response = client.get("/healthz")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_readyz_reports_foundation_state(client: FlaskClient) -> None:
    response = client.get("/readyz")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["checks"]["database"] == "ok"
    assert payload["checks"]["heartbeats"] == "not_configured"
    assert payload["checks"]["outbox"] == "not_configured"


def test_readyz_accepts_fresh_heartbeat(client: FlaskClient, app: Flask) -> None:
    database: Database = app.extensions["tunza.db"]
    now = datetime.now(UTC)
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO job_heartbeats "
                "(id, job_name, last_seen_at, created_at, updated_at) "
                "VALUES (:id, :job_name, :last_seen_at, :created_at, :updated_at)"
            ),
            {
                "id": uuid.uuid4().hex,
                "job_name": "planner",
                "last_seen_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )

    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.get_json()["checks"]["heartbeats"] == "ok"


def test_readyz_fails_on_stale_heartbeat(client: FlaskClient, app: Flask) -> None:
    database: Database = app.extensions["tunza.db"]
    stale = datetime.now(UTC) - timedelta(minutes=10)
    with database.engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO job_heartbeats "
                "(id, job_name, last_seen_at, created_at, updated_at) "
                "VALUES (:id, :job_name, :last_seen_at, :created_at, :updated_at)"
            ),
            {
                "id": uuid.uuid4().hex,
                "job_name": "planner",
                "last_seen_at": stale.isoformat(),
                "created_at": stale.isoformat(),
                "updated_at": stale.isoformat(),
            },
        )

    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.get_json()["checks"]["heartbeats"] == "stale"
