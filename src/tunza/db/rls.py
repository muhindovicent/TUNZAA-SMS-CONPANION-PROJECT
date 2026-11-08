"""PostgreSQL row-level-security session context helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

APP_ORG_SETTING = "app.org_id"


def _require_postgres(session: Session) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        raise RuntimeError("Row-level security requires PostgreSQL")
    if session.in_transaction() is not True:
        raise RuntimeError("Tenant context must be set inside an explicit transaction")


def set_tenant_context(session: Session, org_id: uuid.UUID) -> None:
    """Set app.org_id for the current transaction using SET LOCAL semantics."""

    _require_postgres(session)
    session.execute(
        text("SELECT set_config(:setting, :value, true)"),
        {"setting": APP_ORG_SETTING, "value": str(org_id)},
    )


def clear_tenant_context(session: Session) -> None:
    """Remove the tenant context from the current transaction."""

    _require_postgres(session)
    session.execute(
        text("SELECT set_config(:setting, '', true)"),
        {"setting": APP_ORG_SETTING},
    )


def current_tenant_id(session: Session) -> uuid.UUID | None:
    """Return the tenant UUID bound to the current transaction, if any."""

    _require_postgres(session)
    value = session.execute(
        text("SELECT current_setting(:setting, true)"),
        {"setting": APP_ORG_SETTING},
    ).scalar()
    if value is None or str(value) == "":
        return None
    return uuid.UUID(str(value))
