"""Tenant settings and configuration models."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, ForeignKey, JSON, String, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from tunza.db.base import Base, TimestampMixin


class TenantSettings(TimestampMixin, Base):
    """Typed per-tenant configuration for the identity and messaging stages."""

    __tablename__ = "tenant_settings"

    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    languages: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=lambda: ["en", "lg"]
    )
    default_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="en", server_default=text("'en'")
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="Africa/Kampala", server_default=text("'Africa/Kampala'")
    )
    quiet_hours_start: Mapped[str] = mapped_column(
        String(5), nullable=False, default="21:00", server_default=text("'21:00'")
    )
    quiet_hours_end: Mapped[str] = mapped_column(
        String(5), nullable=False, default="06:00", server_default=text("'06:00'")
    )
    sender_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    oidc_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    oidc_issuer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    oidc_client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oidc_client_secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    oidc_allowed_domains: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    def as_public_dict(self) -> dict[str, Any]:
        return {
            "languages": self.languages,
            "default_language": self.default_language,
            "timezone": self.timezone,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "sender_id": self.sender_id,
            "oidc_enabled": self.oidc_enabled,
            "oidc_issuer": self.oidc_issuer,
            "oidc_client_id": self.oidc_client_id,
            "oidc_allowed_domains": self.oidc_allowed_domains,
        }
