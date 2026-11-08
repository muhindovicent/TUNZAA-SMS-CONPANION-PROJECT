"""Identity, invitation, factor and session models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from tunza.db.base import Base, TimestampMixin


class UserRole(StrEnum):
    platform_owner = "platform_owner"
    platform_support = "platform_support"
    org_admin = "org_admin"
    clinical_reviewer = "clinical_reviewer"
    dpo = "dpo"
    supervisor = "supervisor"
    vht = "vht"
    facility_staff = "facility_staff"
    partner_viewer = "partner_viewer"


PLATFORM_ROLES = frozenset({UserRole.platform_owner, UserRole.platform_support})
TENANT_ROLES = frozenset(UserRole) - PLATFORM_ROLES


class UserStatus(StrEnum):
    pending_verification = "pending_verification"
    pending_orientation = "pending_orientation"
    active = "active"
    suspended = "suspended"
    deactivated = "deactivated"


class InvitationStatus(StrEnum):
    pending_approval = "pending_approval"
    approved = "approved"
    accepted = "accepted"
    revoked = "revoked"
    expired = "expired"


class SessionStage(StrEnum):
    phone_verification = "phone_verification"
    mfa_required = "mfa_required"
    factor_setup = "factor_setup"
    orientation = "orientation"
    active = "active"


class MfaKind(StrEnum):
    sms = "sms"
    totp = "totp"
    webauthn = "webauthn"


class OtpPurpose(StrEnum):
    phone_verification = "phone_verification"
    login_mfa = "login_mfa"


class AuthOutcome(StrEnum):
    success = "success"
    failure = "failure"
    denied = "denied"
    locked = "locked"


class User(TimestampMixin, Base):
    """Individual account. Accounts are deactivated, never deleted."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role IN ('platform_owner', 'platform_support') AND org_id IS NULL) "
            "OR (role NOT IN ('platform_owner', 'platform_support') AND org_id IS NOT NULL)",
            name="role_org",
        ),
        UniqueConstraint("phone_hash", name="uq_users_phone_hash"),
        UniqueConstraint("org_id", "email", name="uq_users_org_id_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, validate_strings=True),
        nullable=False,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", native_enum=False, validate_strings=True),
        nullable=False,
        default=UserStatus.pending_verification,
        server_default=text("'pending_verification'"),
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_login_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidentiality_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    orientation_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    access_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    oidc_issuer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)

    @property
    def mfa_required(self) -> bool:
        return self.role is not UserRole.partner_viewer


class Invitation(TimestampMixin, Base):
    """Single-use invitation whose token is stored only as a hash."""

    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint(
            "(role IN ('platform_owner', 'platform_support') AND org_id IS NULL) "
            "OR (role NOT IN ('platform_owner', 'platform_support') AND org_id IS NOT NULL)",
            name="role_org",
        ),
        Index("ix_invitations_org_id_status", "org_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=True,
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, validate_strings=True),
        nullable=False,
    )
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            name="invitation_status",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=InvitationStatus.pending_approval,
        server_default=text("'pending_approval'"),
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    required_approvals: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class InvitationApproval(Base):
    """One distinct approver's approval of an invitation."""

    __tablename__ = "invitation_approvals"
    __table_args__ = (
        UniqueConstraint(
            "invitation_id", "approver_id", name="uq_invitation_approvals_invitation_approver"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    invitation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("invitations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    approver_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approver_role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False, validate_strings=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class AuthSession(TimestampMixin, Base):
    """Server-side session. The cookie carries only the random token."""

    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_user_id_revoked_at", "user_id", "revoked_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    csrf_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[SessionStage] = mapped_column(
        Enum(SessionStage, name="session_stage", native_enum=False, validate_strings=True),
        nullable=False,
        default=SessionStage.active,
        server_default=text("'active'"),
    )
    idle_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class MfaFactor(TimestampMixin, Base):
    """Confirmed second factor. SMS factors carry no TOTP secret."""

    __tablename__ = "mfa_factors"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_mfa_factors_user_id_kind"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[MfaKind] = mapped_column(
        Enum(MfaKind, name="mfa_kind", native_enum=False, validate_strings=True),
        nullable=False,
    )
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    secret_encrypted: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OtpChallenge(Base):
    """Short-lived OTP challenge; only a keyed hash of the code is stored."""

    __tablename__ = "otp_challenges"
    __table_args__ = (
        Index("ix_otp_challenges_user_id_purpose", "user_id", "purpose"),
        Index("ix_otp_challenges_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    purpose: Mapped[OtpPurpose] = mapped_column(
        Enum(OtpPurpose, name="otp_purpose", native_enum=False, validate_strings=True),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default=text("5")
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class AuthEvent(Base):
    """Security event used for lockout, rate limits and later audit export."""

    __tablename__ = "auth_events"
    __table_args__ = (
        Index("ix_auth_events_event_type_created_at", "event_type", "created_at"),
        Index("ix_auth_events_ip_hash_created_at", "ip_hash", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[AuthOutcome] = mapped_column(
        Enum(AuthOutcome, name="auth_outcome", native_enum=False, validate_strings=True),
        nullable=False,
    )
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )


class OidcLoginState(Base):
    """One-time state for an OIDC authorization-code flow."""

    __tablename__ = "oidc_login_states"
    __table_args__ = (Index("ix_oidc_login_states_expires_at", "expires_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
    )
    state_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    code_verifier_encrypted: Mapped[str] = mapped_column(String(1024), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False
    )
