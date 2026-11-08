"""Foundational tenancy, feature-flag and heartbeat models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from tunza.db.base import Base, TimestampMixin


class OrganisationStatus(StrEnum):
    onboarding = "onboarding"
    active = "active"
    suspended = "suspended"
    offboarded = "offboarded"


class Organisation(TimestampMixin, Base):
    """Tenant root. Every business table will carry org_id referencing this row."""

    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[OrganisationStatus] = mapped_column(
        Enum(
            OrganisationStatus,
            name="organisation_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=OrganisationStatus.onboarding,
        server_default=text("'onboarding'"),
    )
    signatory_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signatory_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    offboarded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class FeatureFlag(TimestampMixin, Base):
    """Per-tenant or platform-wide feature switch."""

    __tablename__ = "feature_flags"
    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_feature_flags_org_id_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class JobHeartbeat(TimestampMixin, Base):
    """Last-seen timestamp for schedulers and workers."""

    __tablename__ = "job_heartbeats"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


from tunza.modules.audit import models as _audit_models  # noqa: E402, F401
from tunza.modules.identity import models as _identity_models  # noqa: E402, F401
from tunza.modules.tenancy import models as _tenancy_models  # noqa: E402, F401
