from __future__ import annotations

import pytest
from pydantic import ValidationError

from tunza.config import AppEnv, Settings


def test_development_defaults_are_safe_for_local_use() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env is AppEnv.development
    assert settings.seed_demo_data is False
    assert settings.dev_console_otp is False


def test_production_rejects_sqlite() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env=AppEnv.production,
            database_url="sqlite+pysqlite:///./prod.db",
            secret_key="x" * 40,
        )


def test_production_rejects_demo_data_and_console_otp() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env=AppEnv.production,
            database_url="postgresql+psycopg://user:pass@db:5432/tunza",
            secret_key="x" * 40,
            seed_demo_data=True,
        )
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env=AppEnv.production,
            database_url="postgresql+psycopg://user:pass@db:5432/tunza",
            secret_key="x" * 40,
            dev_console_otp=True,
        )


def test_production_rejects_default_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env=AppEnv.production,
            database_url="postgresql+psycopg://user:pass@db:5432/tunza",
            secret_key="dev-only-change-me-32-characters!!",
        )


def test_production_accepts_safe_postgres_configuration() -> None:
    settings = Settings(
        _env_file=None,
        app_env=AppEnv.production,
        database_url="postgresql+psycopg://user:pass@db:5432/tunza",
        secret_key="x" * 40,
    )
    assert settings.app_env is AppEnv.production


def test_staging_rejects_console_otp() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env=AppEnv.staging, dev_console_otp=True)


def test_incomplete_oidc_configuration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, oidc_enabled=True, oidc_issuer="https://id.example.org")


def test_complete_oidc_configuration_is_accepted() -> None:
    settings = Settings(
        _env_file=None,
        oidc_enabled=True,
        oidc_issuer="https://id.example.org",
        oidc_client_id="tunza",
        oidc_client_secret="client-secret",
    )
    assert settings.oidc_enabled is True
