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

import httpx
import psycopg2
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.utils.config import Settings, get_settings  # noqa: E402

PASSWORD = "Test-Passw0rd!42"


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


# --- real Supabase identities ----------------------------------------------


@pytest.fixture(scope="session")
def supabase(settings: Settings) -> Settings:
    if not (settings.supabase_url and settings.supabase_secret_key and settings.supabase_jwks_url):
        pytest.skip("Supabase credentials are not configured")
    return settings


class Account:
    """A real Supabase auth user holding a genuinely signed token."""

    def __init__(self, auth_id: str, email: str, token: str) -> None:
        self.auth_id = auth_id
        self.email = email
        self.token = token


@pytest.fixture(scope="session")
def account(supabase: Settings) -> Iterator[Account]:
    base = supabase.supabase_url.rstrip("/")
    admin_headers = {
        "apikey": supabase.supabase_secret_key,
        "Authorization": f"Bearer {supabase.supabase_secret_key}",
    }
    email = f"test-{uuid.uuid4().hex[:10]}@example.com"

    created = httpx.post(
        f"{base}/auth/v1/admin/users",
        headers=admin_headers,
        json={"email": email, "password": PASSWORD, "email_confirm": True},
        timeout=30,
    )
    assert created.status_code in (200, 201), created.text
    auth_id = created.json()["id"]

    signed_in = httpx.post(
        f"{base}/auth/v1/token?grant_type=password",
        headers={"apikey": supabase.supabase_publishable_key, "Content-Type": "application/json"},
        json={"email": email, "password": PASSWORD},
        timeout=30,
    )
    assert signed_in.status_code == 200, signed_in.text

    try:
        yield Account(auth_id, email, signed_in.json()["access_token"])
    finally:
        httpx.delete(f"{base}/auth/v1/admin/users/{auth_id}", headers=admin_headers, timeout=30)


@pytest.fixture
def membership(settings: Settings, account: Account) -> Iterator[dict[str, str]]:
    """Provision the auth user into an organization.

    Committed, because the application's own connection pool is a separate
    connection and would not see an open transaction. Removed afterwards.
    """
    conn = psycopg2.connect(settings.database_url, connect_timeout=20)
    cur = conn.cursor()
    cur.execute("insert into organizations (name) values ('Auth Test Org') returning id")
    org_id = cur.fetchone()[0]
    cur.execute(
        """insert into users (supabase_auth_id, email, name, org_id, role)
           values (%s, %s, 'Test User', %s, 'analyst') returning id""",
        (account.auth_id, account.email, org_id),
    )
    user_id = cur.fetchone()[0]
    conn.commit()
    try:
        yield {"org_id": str(org_id), "user_id": str(user_id)}
    finally:
        cur.execute("delete from organizations where id = %s", (org_id,))
        conn.commit()
        cur.close()
        conn.close()
