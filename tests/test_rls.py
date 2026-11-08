from __future__ import annotations

import uuid

import pytest
from flask import Flask
from sqlalchemy.orm import Session

from tunza.db.engine import Database
from tunza.db.rls import clear_tenant_context, current_tenant_id, set_tenant_context


def test_tenant_context_round_trip(app: Flask) -> None:
    database: Database = app.extensions["tunza.db"]
    if database.engine.dialect.name != "postgresql":
        pytest.skip("Row-level security is PostgreSQL-only")

    org_id = uuid.uuid4()
    with Session(database.engine) as session:
        session.begin()
        set_tenant_context(session, org_id)
        assert current_tenant_id(session) == org_id
        clear_tenant_context(session)
        assert current_tenant_id(session) is None
        session.rollback()
