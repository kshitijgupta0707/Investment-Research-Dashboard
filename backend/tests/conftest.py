"""Shared fixtures.

Database-backed tests run inside a transaction that is always rolled back, so
they leave no trace and can be run repeatedly against the real project.
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg2
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.config import Settings, get_settings  # noqa: E402


@pytest.fixture(scope="session")
def settings() -> Settings:
    return get_settings()


@pytest.fixture(scope="session")
def requires_db(settings: Settings) -> None:
    if not settings.database_url:
        pytest.skip("DATABASE_URL is not configured")


@pytest.fixture
def db(settings: Settings, requires_db: None) -> Iterator[Any]:
    """A cursor whose transaction is rolled back when the test finishes."""
    conn = psycopg2.connect(settings.database_url, connect_timeout=20)
    try:
        yield conn.cursor()
    finally:
        conn.rollback()
        conn.close()


def become(cur: Any, auth_id: str) -> None:
    """Impersonate an authenticated end user, so RLS policies apply.

    Sets both claim shapes, since Supabase's auth.uid() has read from each
    across versions.
    """
    cur.execute("reset role")
    claims = json.dumps({"sub": auth_id, "role": "authenticated"})
    cur.execute("select set_config('request.jwt.claims', %s, true)", (claims,))
    cur.execute("select set_config('request.jwt.claim.sub', %s, true)", (auth_id,))
    cur.execute("set local role authenticated")


def as_service(cur: Any) -> None:
    """Return to the privileged role, which RLS does not constrain."""
    cur.execute("reset role")


class Tenants:
    """Ids for the seeded two-organization fixture."""

    def __init__(self) -> None:
        self.auth_ids: dict[str, str] = {}
        self.users: dict[str, str] = {}
        self.reports: dict[str, str] = {}
        self.org_a: str = ""
        self.org_b: str = ""


@pytest.fixture
def tenants(db: Any) -> Tenants:
    """Org A with an admin and two analysts; Org B with one analyst.

    Seeded as the privileged role so RLS does not interfere with setup.
    """
    t = Tenants()
    as_service(db)

    db.execute("insert into organizations (name) values ('Org A') returning id")
    t.org_a = db.fetchone()[0]
    db.execute("insert into organizations (name) values ('Org B') returning id")
    t.org_b = db.fetchone()[0]

    for key, org, role in [
        ("a_admin", t.org_a, "admin"),
        ("a1", t.org_a, "analyst"),
        ("a2", t.org_a, "analyst"),
        ("b1", t.org_b, "analyst"),
    ]:
        t.auth_ids[key] = str(uuid.uuid4())
        db.execute(
            """insert into users (supabase_auth_id, email, org_id, role)
               values (%s, %s, %s, %s) returning id""",
            (t.auth_ids[key], f"{key}@test.invalid", org, role),
        )
        t.users[key] = db.fetchone()[0]

    for key, org in [("a1", t.org_a), ("a2", t.org_a), ("b1", t.org_b)]:
        db.execute(
            """insert into research_reports (org_id, created_by, query_text, structured_result)
               values (%s, %s, %s, %s) returning id""",
            (org, t.users[key], f"query by {key}", json.dumps({"summary": key})),
        )
        t.reports[key] = db.fetchone()[0]

    for key, org, ticker in [("a1", t.org_a, "NVDA"), ("a2", t.org_a, "AMD")]:
        db.execute(
            "insert into watchlist (org_id, user_id, ticker) values (%s, %s, %s)",
            (org, t.users[key], ticker),
        )

    return t
