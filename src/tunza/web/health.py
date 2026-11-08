"""Liveness and readiness endpoints."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.typing import ResponseReturnValue

from tunza.config import Settings
from tunza.db.engine import Database

bp = Blueprint("health", __name__)


@bp.get("/healthz")
def healthz() -> ResponseReturnValue:
    return jsonify({"status": "ok"})


@bp.get("/readyz")
def readyz() -> ResponseReturnValue:
    settings: Settings = current_app.extensions["tunza.settings"]
    database: Database = current_app.extensions["tunza.db"]
    checks = database.readiness(settings.heartbeat_interval_seconds)
    healthy = (
        checks.get("database") == "ok"
        and checks.get("heartbeats") in {"ok", "not_configured"}
        and checks.get("outbox") != "stale"
    )
    return jsonify({"status": "ok" if healthy else "unavailable", "checks": checks}), (
        200 if healthy else 503
    )
