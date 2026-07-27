"""JWT verification and tenant context, against real Supabase-issued tokens.

Creates a throwaway auth user, signs in for a genuine token, and exercises the
dependency through the real application. Everything is removed afterwards.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.config import Settings

pytestmark = pytest.mark.integration

PASSWORD = "Test-Passw0rd!42"


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Entering the context manager runs lifespan, opening the database pool."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="module")
def supabase(settings: Settings) -> Settings:
    if not (settings.supabase_url and settings.supabase_secret_key and settings.supabase_jwks_url):
        pytest.skip("Supabase credentials are not configured")
    return settings


class Account:
    def __init__(self, auth_id: str, email: str, token: str) -> None:
        self.auth_id = auth_id
        self.email = email
        self.token = token


@pytest.fixture(scope="module")
def account(supabase: Settings) -> Iterator[Account]:
    """A real Supabase auth user with a real signed token."""
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
    """Provision the auth user into an organization, committed so the app's
    own connection pool can see it. Removed afterwards."""
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


def me(client: TestClient, token: str | None) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.get("/api/me", headers=headers)


# --- rejection paths --------------------------------------------------------


def test_missing_header_is_401(client: TestClient) -> None:
    assert me(client, None).status_code == 401


def test_malformed_token_is_401(client: TestClient) -> None:
    assert me(client, "not-a-jwt").status_code == 401


def test_tampered_signature_is_401(client: TestClient, account: Account) -> None:
    header, payload, signature = account.token.split(".")
    assert me(client, f"{header}.{payload}.{'A' * len(signature)}").status_code == 401


def test_foreign_signing_key_is_401(client: TestClient, account: Account) -> None:
    """A token we sign ourselves must not be accepted, whatever it claims."""
    import jwt

    forged = jwt.encode(
        {"sub": account.auth_id, "aud": "authenticated"},
        "a-secret-we-invented-locally",
        algorithm="HS256",
    )
    assert me(client, forged).status_code == 401


def test_valid_token_without_membership_is_403(client: TestClient, account: Account) -> None:
    """Authenticated by Supabase, but not provisioned in this application."""
    assert me(client, account.token).status_code == 403


# --- resolved context -------------------------------------------------------


def test_valid_token_with_membership_resolves_context(
    client: TestClient, account: Account, membership: dict[str, str]
) -> None:
    response = me(client, account.token)
    assert response.status_code == 200

    body = response.json()
    assert body["id"] == membership["user_id"], "should expose our users.id, not the auth id"
    assert body["auth_id"] == account.auth_id
    assert body["org_id"] == membership["org_id"]
    assert body["role"] == "analyst"
    assert body["email"] == account.email


def test_role_is_read_from_the_database_not_the_token(
    client: TestClient, settings: Settings, account: Account, membership: dict[str, str]
) -> None:
    """Changing the stored role takes effect on the same unchanged token."""
    conn = psycopg2.connect(settings.database_url, connect_timeout=20)
    cur = conn.cursor()
    cur.execute("update users set role = 'admin' where supabase_auth_id = %s", (account.auth_id,))
    conn.commit()
    cur.close()
    conn.close()

    assert me(client, account.token).json()["role"] == "admin"
