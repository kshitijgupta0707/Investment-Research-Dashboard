"""Request ids and structured log output."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app as real_app
from app.utils.context import get_request_id, set_request_id
from app.utils.logging import JsonFormatter


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    with TestClient(real_app) as test_client:
        yield test_client


# --- request id -------------------------------------------------------------


def test_response_carries_a_request_id(client: TestClient) -> None:
    response = client.get("/")
    assert response.headers.get("x-request-id")


def test_request_id_matches_the_envelope(client: TestClient) -> None:
    """The header and the body must agree, or correlation is useless."""
    response = client.get("/")
    assert response.json()["meta"]["request_id"] == response.headers["x-request-id"]


def test_inbound_request_id_is_honoured(client: TestClient) -> None:
    """Lets a caller trace one request across service boundaries."""
    response = client.get("/", headers={"X-Request-ID": "caller-supplied-id"})
    assert response.headers["x-request-id"] == "caller-supplied-id"
    assert response.json()["meta"]["request_id"] == "caller-supplied-id"


def test_each_request_gets_a_distinct_id(client: TestClient) -> None:
    first = client.get("/").headers["x-request-id"]
    second = client.get("/").headers["x-request-id"]
    assert first != second


def test_error_responses_are_correlatable(client: TestClient) -> None:
    response = client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["meta"]["request_id"] == response.headers["x-request-id"]


# --- log format -------------------------------------------------------------


def record(**context: object) -> logging.LogRecord:
    rec = logging.LogRecord("app.request", logging.INFO, __file__, 1, "request", None, None)
    rec.context = context  # type: ignore[attr-defined]
    return rec


def test_log_line_is_json_with_expected_fields() -> None:
    line = JsonFormatter().format(
        record(method="GET", path="/api/me", status_code=200, latency_ms=12.3, org_id="org-1")
    )
    payload = json.loads(line)
    assert payload["level"] == "INFO"
    assert payload["message"] == "request"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/me"
    assert payload["status_code"] == 200
    assert payload["latency_ms"] == 12.3
    assert payload["org_id"] == "org-1"
    assert "timestamp" in payload


def test_log_line_includes_the_active_request_id() -> None:
    token = set_request_id("abc123")
    try:
        payload = json.loads(JsonFormatter().format(record(path="/")))
        assert payload["request_id"] == "abc123"
    finally:
        from app.utils.context import reset_request_id

        reset_request_id(token)


def test_request_id_is_absent_outside_a_request() -> None:
    assert get_request_id() is None
    assert "request_id" not in json.loads(JsonFormatter().format(record()))


def test_exceptions_are_serialised_into_the_line() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        rec = record(path="/")
        rec.exc_info = sys.exc_info()
        payload = json.loads(JsonFormatter().format(rec))

    assert "ValueError: boom" in payload["exception"]


def test_formatter_output_is_a_single_line() -> None:
    """Multi-line output would break line-oriented log shipping."""
    line = JsonFormatter().format(record(path="/a\nb"))
    assert "\n" not in line


# --- tenant context reaches the log -----------------------------------------


@pytest.mark.integration
def test_authenticated_request_logs_tenant_context(
    client: TestClient, account, membership, caplog
) -> None:
    """The access log must identify who called and for which org.

    This is the value of the whole layer: a log search can answer "what did
    this organization do" without correlating against another system.
    """
    with caplog.at_level(logging.INFO, logger="app.request"):
        response = client.get("/api/me", headers={"Authorization": f"Bearer {account.token}"})
    assert response.status_code == 200

    entries = [r for r in caplog.records if r.name == "app.request"]
    assert entries, "no access log line was emitted"

    context = entries[-1].context
    assert context["user_id"] == membership["user_id"]
    assert context["org_id"] == membership["org_id"]
    assert context["path"] == "/api/me"
    assert context["status_code"] == 200
    assert context["latency_ms"] > 0


@pytest.mark.integration
def test_anonymous_request_logs_no_tenant(client: TestClient, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="app.request"):
        client.get("/api/me")

    context = [r for r in caplog.records if r.name == "app.request"][-1].context
    assert context["user_id"] is None
    assert context["org_id"] is None
    assert context["status_code"] == 401
