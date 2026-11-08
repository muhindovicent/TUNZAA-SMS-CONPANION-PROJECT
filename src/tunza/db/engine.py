"""Engine construction and readiness probes."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from tunza.config import Settings


class Database:
    """Owns the SQLAlchemy engine and session factory for the process."""

    def __init__(self, settings: Settings) -> None:
        connect_args: dict[str, Any] = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        self.engine: Engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            connect_args=connect_args,
            future=True,
        )
        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
            class_=Session,
        )

    def dispose(self) -> None:
        self.engine.dispose()

    def check_connection(self) -> None:
        with self.engine.connect() as connection:
            connection.execute(text("SELECT 1"))

    def readiness(self, heartbeat_interval_seconds: int) -> dict[str, str]:
        checks: dict[str, str] = {}
        try:
            self.check_connection()
            checks["database"] = "ok"
        except SQLAlchemyError:
            checks["database"] = "fail"
            return checks
        checks["heartbeats"] = self._heartbeat_status(heartbeat_interval_seconds)
        checks["outbox"] = self._outbox_status()
        return checks

    def _table_exists(self, table_name: str) -> bool:
        return inspect(self.engine).has_table(table_name)

    def _heartbeat_status(self, heartbeat_interval_seconds: int) -> str:
        if not self._table_exists("job_heartbeats"):
            return "not_configured"
        with self.engine.connect() as connection:
            value = connection.execute(
                text("SELECT MAX(last_seen_at) FROM job_heartbeats")
            ).scalar()
        if value is None:
            return "not_configured"
        last_seen = _as_utc(value)
        stale_before = datetime.now(UTC) - timedelta(seconds=2 * heartbeat_interval_seconds)
        return "ok" if last_seen >= stale_before else "stale"

    def _outbox_status(self) -> str:
        if not self._table_exists("outbox"):
            return "not_configured"
        with self.engine.connect() as connection:
            depth: int = int(
                connection.execute(
                    text("SELECT COUNT(*) FROM outbox WHERE sent_at IS NULL")
                ).scalar_one()
            )
        return f"depth={depth}"


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value))
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
