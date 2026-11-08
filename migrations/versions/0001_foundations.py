"""Foundational tenancy, feature-flag and heartbeat tables.

Revision ID: 0001_foundations
Revises:
Create Date: 2026-10-31

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_foundations"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

organisation_status = sa.Enum(
    "onboarding",
    "active",
    "suspended",
    "offboarded",
    name="organisation_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("status", organisation_status, server_default="onboarding", nullable=False),
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
        sa.PrimaryKeyConstraint("id", name="pk_organisations"),
        sa.UniqueConstraint("slug", name="uq_organisations_slug"),
    )

    op.create_table(
        "feature_flags",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
            name="fk_feature_flags_org_id_organisations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feature_flags"),
        sa.UniqueConstraint("org_id", "key", name="uq_feature_flags_org_id_key"),
    )
    op.create_index("ix_feature_flags_org_id", "feature_flags", ["org_id"], unique=False)

    op.create_table(
        "job_heartbeats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_name", sa.String(length=100), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_job_heartbeats"),
        sa.UniqueConstraint("job_name", name="uq_job_heartbeats_job_name"),
    )


def downgrade() -> None:
    op.drop_table("job_heartbeats")
    op.drop_index("ix_feature_flags_org_id", table_name="feature_flags")
    op.drop_table("feature_flags")
    op.drop_table("organisations")
