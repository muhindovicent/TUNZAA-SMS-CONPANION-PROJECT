from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import text

from tunza.app import create_app
from tunza.config import AppEnv, Settings
from tunza.db import models as _models  # noqa: F401
from tunza.db.base import Base
from tunza.db.engine import Database


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_url = os.environ.get("TEST_DATABASE_URL")
    return Settings(
        app_env=AppEnv.test,
        database_url=database_url or f"sqlite+pysqlite:///{tmp_path / 'tunza-test.db'}",
        secret_key="test-secret-key-0123456789abcdef",
        log_level="WARNING",
    )


@pytest.fixture
def app(settings: Settings) -> Iterator[Flask]:
    application = create_app(settings)
    database: Database = application.extensions["tunza.db"]
    Base.metadata.create_all(database.engine)
    with database.engine.begin() as connection:
        connection.execute(text("DELETE FROM job_heartbeats"))
    yield application
    database.dispose()


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
