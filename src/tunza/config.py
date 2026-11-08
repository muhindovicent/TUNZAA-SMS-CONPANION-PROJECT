"""Environment-driven application settings with production safety guards."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-me-32-characters!!"  # noqa: S105  # nosec B105


class AppEnv(StrEnum):
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


class SmsProviderName(StrEnum):
    console = "console"
    africastalking = "africastalking"


class Settings(BaseSettings):
    """Runtime configuration loaded from the environment or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = AppEnv.development
    app_name: str = "Tunza"
    public_base_url: str = "http://localhost:5000"
    secret_key: SecretStr = SecretStr(DEV_SECRET)
    database_url: str = "sqlite+pysqlite:///./tunza-dev.db"
    log_level: str = "INFO"
    timezone: str = "Africa/Kampala"
    heartbeat_interval_seconds: int = Field(default=60, ge=5)
    seed_demo_data: bool = False
    dev_console_otp: bool = False

    field_encryption_key: SecretStr | None = None
    phone_hmac_key: SecretStr | None = None
    session_cookie_secure: bool = False
    session_privileged_idle_seconds: int = Field(default=900, ge=60)
    session_idle_seconds: int = Field(default=1800, ge=60)
    session_absolute_seconds: int = Field(default=43200, ge=300)
    invitation_ttl_hours: int = Field(default=72, ge=1, le=168)
    otp_ttl_seconds: int = Field(default=300, ge=60, le=900)
    otp_max_attempts: int = Field(default=5, ge=1, le=10)
    otp_resend_seconds: int = Field(default=60, ge=30, le=300)
    login_max_failures: int = Field(default=5, ge=3, le=10)
    login_lockout_minutes: int = Field(default=15, ge=1, le=60)
    login_ip_limit: int = Field(default=20, ge=5, le=100)
    login_ip_window_seconds: int = Field(default=900, ge=60, le=3600)

    sms_provider: SmsProviderName = SmsProviderName.console
    africastalking_username: str | None = None
    africastalking_api_key: SecretStr | None = None
    africastalking_sender_id: str | None = None
    africastalking_base_url: str = "https://api.africastalking.com"
    africastalking_sandbox: bool = True

    oidc_enabled: bool = False
    oidc_issuer: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_scopes: str = "openid email profile"

    @model_validator(mode="after")
    def validate_production_safety(self) -> Self:
        secret = self.secret_key.get_secret_value()
        production_like = self.app_env in {AppEnv.staging, AppEnv.production}
        if self.app_env is AppEnv.production:
            if self.seed_demo_data:
                raise ValueError("SEED_DEMO_DATA must be false in production")
            if self.dev_console_otp:
                raise ValueError("DEV_CONSOLE_OTP must be false in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("SQLite is not allowed in production")
            if secret.startswith("dev-only"):
                raise ValueError("SECRET_KEY must be replaced in production")
            if len(secret) < 32:
                raise ValueError("SECRET_KEY must be at least 32 characters in production")
        if self.app_env is AppEnv.staging and (self.seed_demo_data or self.dev_console_otp):
            raise ValueError("Staging must not enable demo data or the console OTP path")
        if production_like:
            if not self.session_cookie_secure:
                raise ValueError("SESSION_COOKIE_SECURE must be true outside development")
            if not self.public_base_url.startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL must use HTTPS outside development")
            if self.field_encryption_key is None or self.phone_hmac_key is None:
                raise ValueError(
                    "FIELD_ENCRYPTION_KEY and PHONE_HMAC_KEY are required outside development"
                )
        if self.oidc_enabled and not (
            self.oidc_issuer and self.oidc_client_id and self.oidc_client_secret
        ):
            raise ValueError("OIDC settings are incomplete")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""

    return Settings()
