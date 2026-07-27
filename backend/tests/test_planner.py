"""Turn 1 -- tool selection.

Parsing and error translation are tested against stubbed responses. Whether
Claude *chooses* correctly is the acceptance-query test at the bottom, which
needs a funded API key and skips without one.
"""

from __future__ import annotations

from typing import Any

import anthropic
import httpx
import pytest

from app.agent import planner
from app.agent.client import translate_error
from app.agent.tools import KNOWLEDGE_BASE, MARKET_DATA, NEWS_SENTIMENT
from app.integrations.errors import (
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)

# --- stubs ------------------------------------------------------------------


class Block:
    def __init__(self, type: str, **kwargs: Any) -> None:
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class Usage:
    input_tokens = 100
    output_tokens = 20


class Response:
    def __init__(self, content: list[Block], stop_reason: str = "tool_use") -> None:
        self.content = content
        self.stop_reason = stop_reason
        self.model = "claude-sonnet-5"
        self.usage = Usage()


def tool_use(name: str, arguments: dict[str, Any], id: str = "toolu_1") -> Block:
    return Block("tool_use", id=id, name=name, input=arguments)


def text(value: str) -> Block:
    return Block("text", text=value)


@pytest.fixture
def respond_with(monkeypatch: pytest.MonkeyPatch):
    """Make the planner see a chosen Claude response without calling the API."""

    def apply(*blocks: Block, stop_reason: str = "tool_use") -> None:
        async def fake_create(**_: Any) -> Response:
            return Response(list(blocks), stop_reason)

        monkeypatch.setattr(
            planner, "get_client", lambda: type("C", (), {"messages": type("M", (), {"create": staticmethod(fake_create)})()})()
        )

    return apply


@pytest.fixture
def fail_with(monkeypatch: pytest.MonkeyPatch):
    def apply(exc: Exception) -> None:
        async def fake_create(**_: Any) -> Response:
            raise exc

        monkeypatch.setattr(
            planner, "get_client", lambda: type("C", (), {"messages": type("M", (), {"create": staticmethod(fake_create)})()})()
        )

    return apply


# --- parsing ----------------------------------------------------------------


async def test_single_tool_call_is_parsed(respond_with) -> None:
    respond_with(tool_use(NEWS_SENTIMENT, {"tickers": ["TSLA"], "days": 14}))

    plan = await planner.plan_query("latest news on Tesla?")
    assert plan.tool_names == [NEWS_SENTIMENT]
    assert plan.tool_calls[0].arguments["tickers"] == ["TSLA"]
    assert plan.used_tools


async def test_multiple_tool_calls_preserve_order(respond_with) -> None:
    respond_with(
        tool_use(MARKET_DATA, {"tickers": ["NVDA"]}, id="a"),
        tool_use(NEWS_SENTIMENT, {"tickers": ["NVDA"]}, id="b"),
        tool_use(KNOWLEDGE_BASE, {"query": "risks"}, id="c"),
    )

    plan = await planner.plan_query("overview of NVIDIA")
    assert plan.tool_names == [MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE]


async def test_tool_use_ids_are_kept(respond_with) -> None:
    """Turn 2 matches each result to its request by this id."""
    respond_with(tool_use(MARKET_DATA, {"tickers": ["NVDA"]}, id="toolu_xyz"))

    plan = await planner.plan_query("NVIDIA price")
    assert plan.tool_calls[0].id == "toolu_xyz"


async def test_zero_tools_returns_a_direct_answer(respond_with) -> None:
    """'What is a P/E ratio?' is answered, not routed."""
    respond_with(text("A P/E ratio divides share price by earnings per share."), stop_reason="end_turn")

    plan = await planner.plan_query("What is a P/E ratio?")
    assert plan.tool_names == []
    assert not plan.used_tools
    assert plan.direct_answer and "earnings per share" in plan.direct_answer


async def test_commentary_alongside_tool_calls_is_not_an_answer(respond_with) -> None:
    """Planner chatter is internal; only a no-tool response answers the user."""
    respond_with(
        text("I'll look up the latest coverage."),
        tool_use(NEWS_SENTIMENT, {"tickers": ["TSLA"]}),
    )

    plan = await planner.plan_query("news on Tesla")
    assert plan.direct_answer is None
    assert plan.tool_names == [NEWS_SENTIMENT]


# --- malformed model output -------------------------------------------------


async def test_unknown_tool_is_dropped(respond_with) -> None:
    respond_with(
        tool_use("get_weather", {"city": "Paris"}, id="a"),
        tool_use(MARKET_DATA, {"tickers": ["NVDA"]}, id="b"),
    )

    plan = await planner.plan_query("...")
    assert plan.tool_names == [MARKET_DATA], "one bad call must not lose the good one"


async def test_invalid_arguments_are_dropped(respond_with) -> None:
    """Better a partial report than no report."""
    respond_with(
        tool_use(MARKET_DATA, {"tickers": "NVDA"}, id="a"),  # string, not a list
        tool_use(KNOWLEDGE_BASE, {"query": "risks"}, id="b"),
    )

    plan = await planner.plan_query("...")
    assert plan.tool_names == [KNOWLEDGE_BASE]


async def test_empty_response_is_not_a_crash(respond_with) -> None:
    respond_with(stop_reason="end_turn")

    plan = await planner.plan_query("...")
    assert plan.tool_names == [] and plan.direct_answer is None


# --- error translation ------------------------------------------------------


def status_error(cls: type, status: int, message: str = "boom") -> Exception:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, json={"error": {"message": message}})
    return cls(message, response=response, body={"error": {"message": message}})


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (anthropic.APITimeoutError(httpx.Request("POST", "https://x")), UpstreamTimeout),
        (status_error(anthropic.RateLimitError, 429), UpstreamRateLimited),
        (status_error(anthropic.AuthenticationError, 401), UpstreamUnavailable),
        (status_error(anthropic.InternalServerError, 500), UpstreamUnavailable),
    ],
)
def test_sdk_errors_map_to_our_taxonomy(exc: Exception, expected: type) -> None:
    assert isinstance(translate_error(exc), expected)


def test_bad_request_keeps_the_provider_message() -> None:
    """A 400 is our own misconfiguration; the reason is the only useful part."""
    translated = translate_error(status_error(anthropic.BadRequestError, 400, "credit balance is too low"))
    assert "credit balance is too low" in str(translated)


async def test_planner_raises_our_error_not_the_sdks(fail_with) -> None:
    fail_with(status_error(anthropic.RateLimitError, 429))

    with pytest.raises(UpstreamRateLimited):
        await planner.plan_query("...")


# --- the real thing ---------------------------------------------------------

ACCEPTANCE_CASES = [
    ("What's the latest news on Tesla?", {NEWS_SENTIMENT}),
    ("What's NVIDIA's current P/E and market cap?", {MARKET_DATA}),
    (
        "Give me a quick overview of Tesla - stock performance this quarter, "
        "major news in the last 30 days, and key risks",
        {MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE},
    ),
    (
        "Analyze NVIDIA's Q3 earnings, compare revenue growth with AMD and Intel, "
        "summarize competitive threats and news sentiment, give a risk assessment",
        {MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE},
    ),
    (
        "Compare the balance sheets of JPMorgan, Goldman Sachs, and Morgan Stanley",
        {MARKET_DATA, KNOWLEDGE_BASE},
    ),
    ("What is a P/E ratio?", set()),
]


@pytest.mark.integration
@pytest.mark.parametrize(("query", "expected"), ACCEPTANCE_CASES, ids=lambda v: None)
async def test_acceptance_queries_select_the_right_tools(
    settings, query: str, expected: set[str]
) -> None:
    """The single most scrutinised behaviour in the brief.

    Needs a funded ANTHROPIC_API_KEY; skips otherwise.
    """
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY is not configured")

    try:
        plan = await planner.plan_query(query)
    except UpstreamUnavailable as exc:
        if "credit balance" in str(exc):
            pytest.skip("Anthropic account has no credit")
        raise

    assert set(plan.tool_names) == expected, f"selected {plan.tool_names} for: {query}"
