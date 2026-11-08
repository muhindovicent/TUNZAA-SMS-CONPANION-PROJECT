"""Audit helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from tunza.modules.audit.models import AuditLog


def record_audit(
    session: Session,
    *,
    action: str,
    actor_user_id: uuid.UUID | None = None,
    org_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | uuid.UUID | None = None,
    ip_hash: str | None = None,
    user_agent_hash: str | None = None,
    detail: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        org_id=org_id,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash,
        detail=detail,
    )
    session.add(row)
    return row
