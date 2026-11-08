from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_initial_migration_creates_foundation_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "migrate.db"
    database_url = f"sqlite+pysqlite:///{database_path}"

    config = Config("alembic.ini")
    config.attributes["url_override"] = database_url
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()

    assert {
        "alembic_version",
        "organisations",
        "feature_flags",
        "job_heartbeats",
    } <= tables
