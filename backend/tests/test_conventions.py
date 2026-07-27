"""Response envelope, error mapping and health.

The envelope tests run against a throwaway app so every status code can be
provoked deliberately; the health test needs the real one.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.testclient import TestClient

from app.main import app as real_app
from app.middleware.errors import code_for, register_exception_handlers

# --- status code -> error code ---------------------------------------------


@pytest.mark.parametrize(
    ("status_code", "expected"),
    [
        (400, "VALIDATION_ERROR"),
        (401, "UNAUTHENTICATED"),
        (403, "FORBIDDEN"),
        (404, "NOT_FOUND"),
        (429, "RATE_LIMITED"),
        (502, "UPSTREAM_ERROR"),
        (504, "UPSTREAM_TIMEOUT"),
        (418, "CLIENT_ERROR"),
        (599, "INTERNAL_ERROR"),
    ],
)
def test_code_for(status_code: int, expected: str) -> None:
    assert code_for(status_code) == expected


# --- envelope shape ---------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom(status_code: int = Query(...)) -> None:
        raise HTTPException(status_code=status_code, detail="deliberate failure")

    @app.get("/needs-int")
    async def needs_int(count: int = Query(...)) -> dict[str, int]:
        return {"count": count}

    @app.get("/unhandled")
    async def unhandled() -> None:
        raise RuntimeError("secret internal detail")

    return TestClient(app, raise_server_exceptions=False)


def test_error_envelope_shape(client: TestClient) -> None:
    body = client.get("/boom", params={"status_code": 403}).json()
    assert body["success"] is False
    assert body["data"] is None
    assert body["error"]["code"] == "FORBIDDEN"
    assert body["error"]["message"] == "deliberate failure"
    assert "timestamp" in body["meta"]


@pytest.mark.parametrize(
    ("status_code", "code"),
    [(401, "UNAUTHENTICATED"), (403, "FORBIDDEN"), (404, "NOT_FOUND"), (504, "UPSTREAM_TIMEOUT")],
)
def test_status_codes_map_to_error_codes(client: TestClient, status_code: int, code: str) -> None:
    response = client.get("/boom", params={"status_code": status_code})
    assert response.status_code == status_code
    assert response.json()["error"]["code"] == code


def test_validation_failure_is_400_with_details(client: TestClient) -> None:
    """FastAPI defaults to 422; the contract specifies 400."""
    response = client.get("/needs-int", params={"count": "abc"})
    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"], "should say which field failed"


def test_unhandled_error_does_not_leak_internals(client: TestClient) -> None:
    response = client.get("/unhandled")
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in response.text


def test_unknown_route_is_enveloped_404(client: TestClient) -> None:
    body = client.get("/no-such-path").json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"


# --- the real application ---------------------------------------------------


@pytest.fixture(scope="module")
def live() -> Iterator[TestClient]:
    with TestClient(real_app) as test_client:
        yield test_client


def test_root_is_enveloped(live: TestClient) -> None:
    body = live.get("/").json()
    assert body["success"] is True
    assert body["data"]["service"] == "investment-research-dashboard-api"


@pytest.mark.integration
def test_health_reports_database_up(live: TestClient) -> None:
    response = live.get("/health")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["database"] == "up"


def test_unauthenticated_error_is_enveloped(live: TestClient) -> None:
    response = live.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers.get("www-authenticate") == "Bearer", "challenge header must survive"
