"""Row-Level Security policies.

These assert what the *database* permits when reached over a user JWT, which is
the backstop layer. The primary tenant defence is the org_id filter applied in
application code -- see test_auth.py and the reports API tests.

Every test runs inside a transaction that is rolled back afterwards.
"""

from __future__ import annotations

from typing import Any

import psycopg2
import pytest

from tests.conftest import Tenants, as_service, become

pytestmark = pytest.mark.integration


# --- helper resolution ------------------------------------------------------


def test_helpers_resolve_identity_from_jwt(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute(
        "select public.current_org_id(), public.current_app_user_id(), public.current_app_role()"
    )
    org_id, user_id, role = db.fetchone()
    assert str(org_id) == tenants.org_a
    assert str(user_id) == tenants.users["a1"]
    assert role == "analyst"


# --- tenant isolation -------------------------------------------------------


def test_member_sees_every_report_in_their_org(db: Any, tenants: Tenants) -> None:
    """Reports are a shared workspace within an organization."""
    become(db, tenants.auth_ids["a1"])
    db.execute("select count(*) from research_reports")
    assert db.fetchone()[0] == 2


def test_cannot_read_another_orgs_report_by_id(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute("select count(*) from research_reports where id = %s", (tenants.reports["b1"],))
    assert db.fetchone()[0] == 0


def test_sees_only_own_org_and_members(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute("select count(*) from organizations")
    assert db.fetchone()[0] == 1
    db.execute("select count(*) from users")
    assert db.fetchone()[0] == 3


def test_other_tenant_sees_only_its_own(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["b1"])
    db.execute("select count(*) from research_reports")
    assert db.fetchone()[0] == 1
    db.execute("select count(*) from research_reports where id = %s", (tenants.reports["a1"],))
    assert db.fetchone()[0] == 0


def test_watchlist_is_per_user_not_per_org(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute("select ticker from watchlist")
    assert [row[0] for row in db.fetchall()] == ["NVDA"]


def test_caller_without_identity_sees_nothing(db: Any, tenants: Tenants) -> None:
    as_service(db)
    db.execute("select set_config('request.jwt.claims', '', true)")
    db.execute("select set_config('request.jwt.claim.sub', '', true)")
    db.execute("set local role authenticated")
    db.execute("select count(*) from research_reports")
    assert db.fetchone()[0] == 0


# --- ownership --------------------------------------------------------------


def test_creator_may_update_own_report(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute("update research_reports set tags = %s where id = %s", (["mine"], tenants.reports["a1"]))
    assert db.rowcount == 1


def test_analyst_may_not_touch_a_colleagues_report(db: Any, tenants: Tenants) -> None:
    """A denied write matches no rows rather than raising."""
    become(db, tenants.auth_ids["a1"])
    db.execute("update research_reports set tags = %s where id = %s", (["x"], tenants.reports["a2"]))
    assert db.rowcount == 0
    db.execute("delete from research_reports where id = %s", (tenants.reports["a2"],))
    assert db.rowcount == 0


def test_admin_may_modify_and_delete_a_members_report(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a_admin"])
    db.execute("update research_reports set tags = %s where id = %s", (["by-admin"], tenants.reports["a2"]))
    assert db.rowcount == 1
    db.execute("delete from research_reports where id = %s", (tenants.reports["a2"],))
    assert db.rowcount == 1


# --- forged writes ----------------------------------------------------------


def test_cannot_create_a_report_as_another_user(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute("savepoint sp")
    with pytest.raises(psycopg2.Error):
        db.execute(
            """insert into research_reports (org_id, created_by, query_text, structured_result)
               values (%s, %s, 'forged', '{}')""",
            (tenants.org_a, tenants.users["a2"]),
        )
    db.execute("rollback to savepoint sp")


def test_cannot_write_into_another_org(db: Any, tenants: Tenants) -> None:
    become(db, tenants.auth_ids["a1"])
    db.execute("savepoint sp")
    with pytest.raises(psycopg2.Error):
        db.execute(
            """insert into research_reports (org_id, created_by, query_text, structured_result)
               values (%s, %s, 'cross-org', '{}')""",
            (tenants.org_b, tenants.users["a1"]),
        )
    db.execute("rollback to savepoint sp")
