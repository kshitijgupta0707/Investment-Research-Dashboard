"""Turn 1 -- tool selection.

Parsing and error translation are tested against stubbed responses. Whether
the model *chooses* correctly is the acceptance-query test at the bottom, which
needs a working API key and skips without one.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.agent import planner
from app.agent.client import translate_error
from app.agent.tools import KNOWLEDGE_BASE, MARKET_DATA, NEWS_SENTIMENT, OUT_OF_SCOPE
from app.integrations.errors import (
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)

# --- stubs ------------------------------------------------------------------


# Responses are built from the real SDK types rather than duck-typed fakes, so
# these tests fail if the shape the parser reads ever stops matching the shape
# the SDK actually returns.


def tool_use(name: str, arguments: dict[str, Any]) -> types.Part:
    """A function call. Note there is no id -- Gemini does not assign one."""
    return types.Part.from_function_call(name=name, args=arguments)


def text(value: str) -> types.Part:
    return types.Part.from_text(text=value)


def a_response(
    *parts: types.Part, finish_reason: types.FinishReason = types.FinishReason.STOP
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=list(parts)),
                finish_reason=finish_reason,
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20
        ),
        model_version="gemini-2.5-flash",
    )


def _stub_client(monkeypatch: pytest.MonkeyPatch, generate_content: Any) -> None:
    """Patch out the whole `client.aio.models.generate_content` chain."""
    models = type("Models", (), {"generate_content": staticmethod(generate_content)})()
    aio = type("Aio", (), {"models": models})()
    monkeypatch.setattr(planner, "get_client", lambda: type("Client", (), {"aio": aio})())


@pytest.fixture
def respond_with(monkeypatch: pytest.MonkeyPatch):
    """Make the planner see a chosen model response without calling the API."""

    def apply(
        *parts: types.Part, finish_reason: types.FinishReason = types.FinishReason.STOP
    ) -> None:
        async def fake_generate(**_: Any) -> types.GenerateContentResponse:
            return a_response(*parts, finish_reason=finish_reason)

        _stub_client(monkeypatch, fake_generate)

    return apply


@pytest.fixture
def fail_with(monkeypatch: pytest.MonkeyPatch):
    def apply(exc: Exception) -> None:
        async def fake_generate(**_: Any) -> types.GenerateContentResponse:
            raise exc

        _stub_client(monkeypatch, fake_generate)

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
        tool_use(MARKET_DATA, {"tickers": ["NVDA"]}),
        tool_use(NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        tool_use(KNOWLEDGE_BASE, {"query": "risks"}),
    )

    plan = await planner.plan_query("overview of NVIDIA")
    assert plan.tool_names == [MARKET_DATA, NEWS_SENTIMENT, KNOWLEDGE_BASE]


async def test_every_call_gets_a_distinct_id(respond_with) -> None:
    """Turn 2 matches each result to its request by this id.

    Gemini does not label its function calls, so the planner mints the ids. The
    only property the rest of the pipeline depends on is that they are unique
    within one plan.
    """
    respond_with(
        tool_use(MARKET_DATA, {"tickers": ["NVDA"]}),
        tool_use(NEWS_SENTIMENT, {"tickers": ["NVDA"]}),
        tool_use(KNOWLEDGE_BASE, {"query": "risks"}),
    )

    plan = await planner.plan_query("overview of NVIDIA")
    ids = [call.id for call in plan.tool_calls]

    assert len(set(ids)) == len(ids)
    assert all(id_ for id_ in ids), "an empty id would collide in the results map"


async def test_ids_stay_distinct_when_a_tool_repeats(respond_with) -> None:
    """Two calls to the same tool must not collapse onto one id."""
    respond_with(
        tool_use(MARKET_DATA, {"tickers": ["NVDA"]}),
        tool_use(MARKET_DATA, {"tickers": ["AMD"]}),
    )

    plan = await planner.plan_query("compare NVDA and AMD")

    assert len({call.id for call in plan.tool_calls}) == 2


async def test_zero_tools_returns_a_direct_answer(respond_with) -> None:
    """'What is a P/E ratio?' is answered, not routed."""
    respond_with(text("A P/E ratio divides share price by earnings per share."))

    plan = await planner.plan_query("What is a P/E ratio?")
    assert plan.tool_names == []
    assert not plan.used_tools
    assert plan.direct_answer and "earnings per share" in plan.direct_answer


async def test_a_refusal_survives_planning(respond_with) -> None:
    """`reject_out_of_scope` has no handler, so it must not be dropped as unknown.

    The service reads it off the plan and answers 400. If the planner discarded
    it the query would proceed as though the model had never objected.
    """
    respond_with(
        tool_use(OUT_OF_SCOPE, {"reason": "This assistant answers equity research questions."})
    )

    plan = await planner.plan_query("Who is the Prime Minister of India?")
    assert plan.tool_names == [OUT_OF_SCOPE]
    assert plan.tool_calls[0].arguments["reason"].startswith("This assistant")


async def test_a_refusal_missing_its_reason_is_dropped(respond_with) -> None:
    """Validated like any other tool -- a call we cannot render is not usable."""
    respond_with(tool_use(OUT_OF_SCOPE, {}))

    plan = await planner.plan_query("Who is the Prime Minister of India?")
    assert plan.tool_names == []


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
        tool_use("get_weather", {"city": "Paris"}),
        tool_use(MARKET_DATA, {"tickers": ["NVDA"]}),
    )

    plan = await planner.plan_query("...")
    assert plan.tool_names == [MARKET_DATA], "one bad call must not lose the good one"


async def test_invalid_arguments_are_dropped(respond_with) -> None:
    """Better a partial report than no report."""
    respond_with(
        tool_use(MARKET_DATA, {"tickers": "NVDA"}),  # string, not a list
        tool_use(KNOWLEDGE_BASE, {"query": "risks"}),
    )

    plan = await planner.plan_query("...")
    assert plan.tool_names == [KNOWLEDGE_BASE]


async def test_empty_response_is_not_a_crash(respond_with) -> None:
    respond_with()

    plan = await planner.plan_query("...")
    assert plan.tool_names == [] and plan.direct_answer is None


async def test_a_blocked_response_is_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    """A safety block returns no candidates at all, not an empty candidate."""

    async def fake_generate(**_: Any) -> types.GenerateContentResponse:
        return types.GenerateContentResponse(candidates=[])

    _stub_client(monkeypatch, fake_generate)

    plan = await planner.plan_query("...")
    assert plan.tool_names == [] and plan.direct_answer is None


# --- error translation ------------------------------------------------------


def status_error(status: int, message: str = "boom") -> Exception:
    """Build the SDK error for a status.

    The SDK has one class per status *class*, not per status, so the code is
    carried on the instance -- which is why `translate_error` branches on it.
    """
    cls = genai_errors.ClientError if status < 500 else genai_errors.ServerError
    return cls(status, {"error": {"message": message, "status": "ERROR"}})


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (httpx.TimeoutException("timed out"), UpstreamTimeout),
        (status_error(429), UpstreamRateLimited),
        (status_error(401), UpstreamUnavailable),
        (status_error(403), UpstreamUnavailable),
        (status_error(500), UpstreamUnavailable),
        (status_error(503), UpstreamUnavailable),
        (httpx.ConnectError("no route"), UpstreamUnavailable),
    ],
)
def test_sdk_errors_map_to_our_taxonomy(exc: Exception, expected: type) -> None:
    assert isinstance(translate_error(exc), expected)


def test_bad_request_keeps_the_provider_message() -> None:
    """A 400 is our own misconfiguration; the reason is the only useful part."""
    translated = translate_error(status_error(400, "API key not valid"))
    assert "API key not valid" in str(translated)


def test_every_translated_error_names_the_provider() -> None:
    """The envelope reports which upstream failed, so the name has to survive."""
    for exc in (httpx.TimeoutException("x"), status_error(429), status_error(500)):
        assert "gemini" in str(translate_error(exc))


async def test_planner_raises_our_error_not_the_sdks(fail_with) -> None:
    fail_with(status_error(429))

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

    Needs a working GEMINI_API_KEY; skips otherwise.
    """
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    try:
        plan = await planner.plan_query(query)
    except UpstreamRateLimited:
        pytest.skip("Gemini free-tier rate limit reached")
    except UpstreamUnavailable as exc:
        if "quota" in str(exc).lower():
            pytest.skip("Gemini quota exhausted")
        raise

    assert set(plan.tool_names) == expected, f"selected {plan.tool_names} for: {query}"
