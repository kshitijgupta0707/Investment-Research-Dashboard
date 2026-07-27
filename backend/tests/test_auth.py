"""JWT verification and tenant context, against real Supabase-issued tokens.

Creates a throwaway auth user, signs in for a genuine token, and exercises the
dependency through the real application. Everything is removed afterwards.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.utils.config import Settings
from tests.conftest import Account

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Entering the context manager runs lifespan, opening the database pool."""
    with TestClient(app) as test_client:
        yield test_client


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
    assert response.json()["success"] is True

    body = response.json()["data"]
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

    assert me(client, account.token).json()["data"]["role"] == "admin"
