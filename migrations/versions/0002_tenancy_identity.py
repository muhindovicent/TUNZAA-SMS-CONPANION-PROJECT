"""Tenant settings, identity, invitations, factors and sessions.

Revision ID: 0002_tenancy_identity
Revises: 0001_foundations
Create Date: 2026-10-31

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_tenancy_identity"
down_revision: str | None = "0001_foundations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = sa.Enum(
    "platform_owner",
    "platform_support",
    "org_admin",
    "clinical_reviewer",
    "dpo",
    "supervisor",
    "vht",
    "facility_staff",
    "partner_viewer",
    name="user_role",
    native_enum=False,
)
user_status = sa.Enum(
    "pending_verification",
    "pending_orientation",
    "active",
    "suspended",
    "deactivated",
    name="user_status",
    native_enum=False,
)
invitation_status = sa.Enum(
    "pending_approval",
    "approved",
    "accepted",
    "revoked",
    "expired",
    name="invitation_status",
    native_enum=False,
)
session_stage = sa.Enum(
    "phone_verification",
    "mfa_required",
    "factor_setup",
    "orientation",
    "active",
    name="session_stage",
    native_enum=False,
)
mfa_kind = sa.Enum("sms", "totp", "webauthn", name="mfa_kind", native_enum=False)
otp_purpose = sa.Enum(
    "phone_verification", "login_mfa", name="otp_purpose", native_enum=False
)
auth_outcome = sa.Enum(
    "success", "failure", "denied", "locked", name="auth_outcome", native_enum=False
)


def upgrade() -> None:
    op.add_column("organisations", sa.Column("signatory_name", sa.String(length=200), nullable=True))
    op.add_column(
        "organisations", sa.Column("signatory_email", sa.String(length=320), nullable=True)
    )
    op.add_column(
        "organisations",
        sa.Column("offboarded_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("status", user_status, server_default="pending_verification", nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("phone_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidentiality_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("orientation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oidc_issuer", sa.String(length=500), nullable=True),
        sa.Column("oidc_subject", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role IN ('platform_owner', 'platform_support') AND org_id IS NULL) "
            "OR (role NOT IN ('platform_owner', 'platform_support') AND org_id IS NOT NULL)",
            name="ck_users_role_org",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_users_org_id_organisations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("phone_hash", name="uq_users_phone_hash"),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_id_email"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_org_id", "users", ["org_id"], unique=False)
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "tenant_settings",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("languages", sa.JSON(), nullable=False),
        sa.Column("default_language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="Africa/Kampala",
            nullable=False,
        ),
        sa.Column("quiet_hours_start", sa.String(length=5), server_default="21:00", nullable=False),
        sa.Column("quiet_hours_end", sa.String(length=5), server_default="06:00", nullable=False),
        sa.Column("sender_id", sa.String(length=20), nullable=True),
        sa.Column("oidc_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("oidc_issuer", sa.String(length=500), nullable=True),
        sa.Column("oidc_client_id", sa.String(length=255), nullable=True),
        sa.Column("oidc_client_secret_encrypted", sa.String(length=1024), nullable=True),
        sa.Column("oidc_allowed_domains", sa.JSON(), nullable=False),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_tenant_settings_org_id_organisations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_tenant_settings_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("org_id", name="pk_tenant_settings"),
    )

    op.create_table(
        "invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("role", user_role, nullable=False),
        sa.Column("phone_hash", sa.String(length=64), nullable=False),
        sa.Column("phone_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status", invitation_status, server_default="pending_approval", nullable=False
        ),
        sa.Column("requested_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("required_approvals", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_user_id", sa.Uuid(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(role IN ('platform_owner', 'platform_support') AND org_id IS NULL) "
            "OR (role NOT IN ('platform_owner', 'platform_support') AND org_id IS NOT NULL)",
            name="ck_invitations_role_org",
        ),
        sa.ForeignKeyConstraint(
            ["accepted_user_id"],
            ["users.id"],
            name="fk_invitations_accepted_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_invitations_org_id_organisations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_user_id"],
            ["users.id"],
            name="fk_invitations_requested_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invitations"),
        sa.UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
    )
    op.create_index(
        "ix_invitations_org_id_status", "invitations", ["org_id", "status"], unique=False
    )

    op.create_table(
        "invitation_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("approver_id", sa.Uuid(), nullable=False),
        sa.Column("approver_role", user_role, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["approver_id"],
            ["users.id"],
            name="fk_invitation_approvals_approver_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id"],
            ["invitations.id"],
            name="fk_invitation_approvals_invitation_id_invitations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_invitation_approvals"),
        sa.UniqueConstraint(
            "invitation_id",
            "approver_id",
            name="uq_invitation_approvals_invitation_approver",
        ),
    )
    op.create_index(
        "ix_invitation_approvals_invitation_id",
        "invitation_approvals",
        ["invitation_id"],
        unique=False,
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(length=64), nullable=False),
        sa.Column("stage", session_stage, server_default="active", nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_auth_sessions_org_id_organisations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_id_revoked_at",
        "auth_sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "mfa_factors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", mfa_kind, nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("secret_encrypted", sa.String(length=1024), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_mfa_factors_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_mfa_factors"),
        sa.UniqueConstraint("user_id", "kind", name="uq_mfa_factors_user_id_kind"),
    )

    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", otp_purpose, nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("5"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_otp_challenges_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_otp_challenges"),
    )
    op.create_index(
        "ix_otp_challenges_user_id_purpose",
        "otp_challenges",
        ["user_id", "purpose"],
        unique=False,
    )
    op.create_index(
        "ix_otp_challenges_expires_at", "otp_challenges", ["expires_at"], unique=False
    )

    op.create_table(
        "auth_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", auth_outcome, nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_auth_events_org_id_organisations",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_auth_events_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_auth_events"),
    )
    op.create_index(
        "ix_auth_events_event_type_created_at",
        "auth_events",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_auth_events_ip_hash_created_at",
        "auth_events",
        ["ip_hash", "created_at"],
        unique=False,
    )

    op.create_table(
        "oidc_login_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce_hash", sa.String(length=64), nullable=False),
        sa.Column("code_verifier_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("redirect_uri", sa.String(length=500), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_oidc_login_states_org_id_organisations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_oidc_login_states"),
        sa.UniqueConstraint("state_hash", name="uq_oidc_login_states_state_hash"),
    )
    op.create_index(
        "ix_oidc_login_states_expires_at",
        "oidc_login_states",
        ["expires_at"],
        unique=False,
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent_hash", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name="fk_audit_logs_actor_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organisations.id"],
            name="fk_audit_logs_org_id_organisations",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_logs"),
    )
    op.create_index(
        "ix_audit_logs_org_id_created_at",
        "audit_logs",
        ["org_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_action_created_at",
        "audit_logs",
        ["action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_id_created_at", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_oidc_login_states_expires_at", table_name="oidc_login_states")
    op.drop_table("oidc_login_states")
    op.drop_index("ix_auth_events_ip_hash_created_at", table_name="auth_events")
    op.drop_index("ix_auth_events_event_type_created_at", table_name="auth_events")
    op.drop_table("auth_events")
    op.drop_index("ix_otp_challenges_expires_at", table_name="otp_challenges")
    op.drop_index("ix_otp_challenges_user_id_purpose", table_name="otp_challenges")
    op.drop_table("otp_challenges")
    op.drop_table("mfa_factors")
    op.drop_index("ix_auth_sessions_user_id_revoked_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_invitation_approvals_invitation_id", table_name="invitation_approvals")
    op.drop_table("invitation_approvals")
    op.drop_index("ix_invitations_org_id_status", table_name="invitations")
    op.drop_table("invitations")
    op.drop_table("tenant_settings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_table("users")
    op.drop_column("organisations", "offboarded_at")
    op.drop_column("organisations", "signatory_email")
    op.drop_column("organisations", "signatory_name")
