"""The `/api/research/query` endpoint and the orchestration behind it.

The three agent steps are stubbed here -- their own behaviour is covered in
test_planner, test_executor and test_synthesizer. What matters at this level is
the wiring: that history and audit are written on every path, that the recorded
status reflects what actually happened, and that a provider failure reaches the
caller as its own status code rather than a 500.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.errors import (
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.middleware.auth import get_current_user
from app.middleware.errors import register_exception_handlers
from app.routes import research as research_routes
from app.schemas.agent import PlannedToolCall, QueryPlan
from app.schemas.auth import CurrentUser
from app.schemas.execution import ExecutionResult, ToolResult
from app.schemas.report import ResearchReport
from app.services import research as service

# --- stubs ------------------------------------------------------------------


class FakePool:
    """Records what the service wrote, and can be told to fail."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.fetchvals: list[tuple[str, tuple[Any, ...]]] = []
        self.executes: list[tuple[str, tuple[Any, ...]]] = []
        self.fail_on = fail_on
        self.query_id = uuid4()

    async def fetchval(self, sql: str, *args: Any) -> Any:
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("database is down")
        self.fetchvals.append((sql, args))
        return self.query_id

    async def execute(self, sql: str, *args: Any) -> None:
        if self.fail_on and self.fail_on in sql:
            raise RuntimeError("database is down")
        self.executes.append((sql, args))

    # --- convenience views over what was recorded ---

    @property
    def history(self) -> tuple[Any, ...]:
        assert self.fetchvals, "no history row was written"
        return self.fetchvals[0][1]

    @property
    def history_status(self) -> str:
        return self.history[4]

    @property
    def history_tools(self) -> list[str]:
        return self.history[3]

    @property
    def audit(self) -> tuple[Any, ...]:
        assert self.executes, "no audit entry was written"
        return self.executes[0][1]


USER = CurrentUser(
    id=UUID("11111111-1111-1111-1111-111111111111"),
    auth_id=UUID("22222222-2222-2222-2222-222222222222"),
    email="analyst@test.invalid",
    org_id=UUID("33333333-3333-3333-3333-333333333333"),
    role="analyst",
)


def a_report(*, partial: bool = False, failed: list[str] | None = None) -> ResearchReport:
    return ResearchReport(
        summary="NVIDIA is performing strongly.",
        sections=[
            {
                "title": "Overview",
                "type": "text",
                "content": {"text": "Revenue grew."},
                "confidence": "high",
                "sources": [{"type": "api", "label": "yfinance"}],
            }
        ],
        partial=partial,
        failed_tools=failed or [],
        generated_at=datetime.now(UTC),
    )


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch):
    """Stub the three agent steps. Returns a handle for varying each one."""

    state: dict[str, Any] = {
        "tools": ["get_market_data"],
        "report": a_report(),
        "plan_error": None,
        "synth_error": None,
        "execution": ExecutionResult(),
    }

    async def fake_plan(query: str) -> QueryPlan:
        if state["plan_error"]:
            raise state["plan_error"]
        return QueryPlan(
            query=query,
            tool_calls=[
                PlannedToolCall(id=f"toolu_{i}", name=name, arguments={})
                for i, name in enumerate(state["tools"])
            ],
            model="claude-sonnet-5",
        )

    async def fake_execute(plan: QueryPlan, ctx: Any = None) -> ExecutionResult:
        return state["execution"]

    async def fake_synthesize(plan: QueryPlan, execution: ExecutionResult) -> ResearchReport:
        if state["synth_error"]:
            raise state["synth_error"]
        return state["report"]

    monkeypatch.setattr(service, "plan_query", fake_plan)
    monkeypatch.setattr(service, "execute_plan", fake_execute)
    monkeypatch.setattr(service, "synthesize", fake_synthesize)
    return state


@pytest.fixture
def client(agent, monkeypatch: pytest.MonkeyPatch):
    """A throwaway app with the identity dependency and the pool substituted."""
    pool = FakePool()
    monkeypatch.setattr(research_routes.db, "get_pool", lambda: pool)

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(research_routes.router)
    app.dependency_overrides[get_current_user] = lambda: USER

    test_client = TestClient(app, raise_server_exceptions=False)
    test_client.pool = pool  # type: ignore[attr-defined]
    return test_client


# --- the service ------------------------------------------------------------


async def test_a_successful_run_is_recorded_as_success(agent) -> None:
    pool = FakePool()

    result = await service.run_research_query(pool, USER, "How is NVIDIA doing?")

    assert result.status == "success"
    assert result.query_id == pool.query_id
    assert pool.history_status == "success"


async def test_the_selected_tools_are_written_to_history(agent) -> None:
    """The durable evidence that tool choice varies per query."""
    agent["tools"] = ["get_news_sentiment", "search_knowledge_base"]
    pool = FakePool()

    result = await service.run_research_query(pool, USER, "Latest on Tesla and its risks?")

    assert result.tools_selected == ["get_news_sentiment", "search_knowledge_base"]
    assert pool.history_tools == ["get_news_sentiment", "search_knowledge_base"]


async def test_a_zero_tool_query_records_an_empty_tool_list(agent) -> None:
    agent["tools"] = []
    pool = FakePool()

    result = await service.run_research_query(pool, USER, "What is a P/E ratio?")

    assert result.tools_selected == []
    assert pool.history_tools == []
    assert pool.history_status == "success"


async def test_a_partial_report_is_recorded_as_partial(agent) -> None:
    agent["report"] = a_report(partial=True, failed=["get_news_sentiment"])
    agent["execution"] = ExecutionResult(
        results=[
            ToolResult(tool_use_id="toolu_0", name="get_market_data", ok=True, data={}),
            ToolResult(tool_use_id="toolu_1", name="get_news_sentiment", ok=False, error="down"),
        ]
    )
    pool = FakePool()

    result = await service.run_research_query(pool, USER, "Overview of NVIDIA")

    assert result.status == "partial"
    assert pool.history_status == "partial"
    assert result.report.failed_tools == ["get_news_sentiment"]


async def test_history_is_scoped_to_the_caller(agent) -> None:
    pool = FakePool()

    await service.run_research_query(pool, USER, "How is NVIDIA doing?")

    org_id, user_id, query_text = pool.history[0], pool.history[1], pool.history[2]
    assert org_id == USER.org_id
    assert user_id == USER.id
    assert query_text == "How is NVIDIA doing?"


async def test_a_successful_run_is_audited(agent) -> None:
    pool = FakePool()

    await service.run_research_query(pool, USER, "How is NVIDIA doing?")

    org_id, user_id, action, entity_type, entity_id, metadata = pool.audit
    assert (org_id, user_id, action) == (USER.org_id, USER.id, service.AUDIT_ACTION)
    assert (entity_type, entity_id) == ("research_query", pool.query_id)
    assert metadata["tools_selected"] == ["get_market_data"]
    assert metadata["status"] == "success"


# --- failure paths ----------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        UpstreamUnavailable("anthropic", "credit balance is too low"),
        UpstreamTimeout("anthropic", "no response within the configured budget"),
        UpstreamRateLimited("anthropic", "request quota exhausted"),
    ],
)
async def test_provider_failures_propagate(agent, error: Exception) -> None:
    """The route layer maps these to a status code; the service must not swallow them."""
    agent["plan_error"] = error
    pool = FakePool()

    with pytest.raises(type(error)):
        await service.run_research_query(pool, USER, "How is NVIDIA doing?")


async def test_a_failed_query_is_still_recorded(agent) -> None:
    """A query that died is exactly the kind a user wants to see in history."""
    agent["plan_error"] = UpstreamUnavailable("anthropic", "down")
    pool = FakePool()

    with pytest.raises(UpstreamUnavailable):
        await service.run_research_query(pool, USER, "How is NVIDIA doing?")

    assert pool.history_status == "failed"
    assert pool.audit[5]["status"] == "failed"


async def test_a_failure_after_planning_records_the_chosen_tools(agent) -> None:
    """Turn 1 succeeded, so which tools it picked is known and worth keeping."""
    agent["tools"] = ["get_market_data", "get_news_sentiment"]
    agent["synth_error"] = UpstreamTimeout("anthropic", "timed out")
    pool = FakePool()

    with pytest.raises(UpstreamTimeout):
        await service.run_research_query(pool, USER, "Overview of NVIDIA")

    assert pool.history_status == "failed"
    assert pool.history_tools == ["get_market_data", "get_news_sentiment"]


async def test_a_recording_failure_does_not_mask_the_real_error(agent) -> None:
    """The caller must learn Claude was down, not that the history insert broke."""
    agent["plan_error"] = UpstreamUnavailable("anthropic", "down")
    pool = FakePool(fail_on="research_queries")

    with pytest.raises(UpstreamUnavailable, match="down"):
        await service.run_research_query(pool, USER, "How is NVIDIA doing?")


async def test_an_audit_failure_does_not_fail_the_request(agent) -> None:
    """The query already ran; refusing to return it over an audit hiccup is worse."""
    pool = FakePool(fail_on="audit_logs")

    result = await service.run_research_query(pool, USER, "How is NVIDIA doing?")

    assert result.status == "success"
    assert pool.executes == []


# --- the endpoint -----------------------------------------------------------


def test_the_endpoint_returns_the_envelope(client) -> None:
    response = client.post("/api/research/query", json={"query_text": "How is NVIDIA doing?"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["error"] is None
    assert body["data"]["report"]["summary"] == "NVIDIA is performing strongly."
    assert body["data"]["tools_selected"] == ["get_market_data"]


def test_the_report_carries_the_full_contract(client) -> None:
    """What the frontend renders -- it never parses free text."""
    body = client.post("/api/research/query", json={"query_text": "How is NVIDIA doing?"}).json()

    report = body["data"]["report"]
    assert set(report) == {"summary", "sections", "partial", "failed_tools", "generated_at"}
    section = report["sections"][0]
    assert section["type"] == "text"
    assert section["confidence"] == "high"
    assert section["sources"][0]["label"] == "yfinance"


@pytest.mark.parametrize(
    "payload",
    [
        {"query_text": ""},
        {"query_text": "  "},
        {"query_text": "hi"},
        {"query_text": "x" * 2001},
        {},
        {"query_text": None},
    ],
)
def test_invalid_input_is_400(client, payload: dict[str, Any]) -> None:
    response = client.post("/api/research/query", json=payload)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_surrounding_whitespace_is_stripped(client) -> None:
    client.post("/api/research/query", json={"query_text": "  How is NVIDIA doing?  "})

    assert client.pool.history[2] == "How is NVIDIA doing?"


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (UpstreamUnavailable("anthropic", "down"), 502, "UPSTREAM_ERROR"),
        (UpstreamTimeout("anthropic", "slow"), 504, "UPSTREAM_TIMEOUT"),
        (UpstreamRateLimited("anthropic", "quota"), 429, "RATE_LIMITED"),
    ],
)
def test_provider_failures_map_to_status_codes(
    client, agent, error: Exception, status: int, code: str
) -> None:
    agent["plan_error"] = error

    response = client.post("/api/research/query", json={"query_text": "How is NVIDIA doing?"})

    assert response.status_code == status
    assert response.json()["error"]["code"] == code


def test_provider_messages_are_not_leaked_to_the_caller(client, agent) -> None:
    """An LLM 400 names our model id or billing state. That is not the analyst's business."""
    agent["plan_error"] = UpstreamUnavailable("anthropic", "credit balance is too low")

    response = client.post("/api/research/query", json={"query_text": "How is NVIDIA doing?"})

    assert "credit balance" not in response.text
    assert response.json()["error"]["message"]


def test_an_unexpected_error_is_still_a_500(client, agent) -> None:
    agent["synth_error"] = RuntimeError("something internal broke")

    response = client.post("/api/research/query", json={"query_text": "How is NVIDIA doing?"})

    assert response.status_code == 500
    assert "something internal broke" not in response.text


def test_the_endpoint_requires_authentication(agent, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the override, the real dependency runs and rejects an anonymous call."""
    monkeypatch.setattr(research_routes.db, "get_pool", lambda: FakePool())

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(research_routes.router)

    response = TestClient(app).post("/api/research/query", json={"query_text": "hello there"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
