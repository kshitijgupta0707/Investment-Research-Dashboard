"""Turn 2 -- synthesis into the fixed report contract.

Covers the three things the frontend depends on: the output always conforms to
the schema or the call raises, the degradation flags come from what actually
happened rather than from the model, and a malformed generation is retried once
before giving up.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.agent import synthesizer
from app.integrations.errors import UpstreamTimeout, UpstreamUnavailable
from app.schemas.agent import PlannedToolCall, QueryPlan
from app.schemas.execution import ExecutionResult, ToolResult
from app.schemas.report import (
    ChartContent,
    CompanyCardContent,
    SentimentContent,
    TableContent,
    TextContent,
)

# --- stubs ------------------------------------------------------------------


class Block:
    def __init__(self, type: str, **kwargs: Any) -> None:
        self.type = type
        for key, value in kwargs.items():
            setattr(self, key, value)


class Usage:
    input_tokens = 500
    output_tokens = 300


class Response:
    def __init__(self, content: list[Block]) -> None:
        self.content = content
        self.model = "claude-sonnet-5"
        self.stop_reason = "tool_use"
        self.usage = Usage()


def emit(payload: dict[str, Any]) -> Block:
    return Block("tool_use", id="toolu_out", name=synthesizer.EMIT_REPORT, input=payload)


class Recorder:
    """Serves canned responses in order and keeps the requests that produced them."""

    def __init__(self, *responses: Response) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Response:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("model called more times than the test allows")
        return self.responses.pop(0)


@pytest.fixture
def respond_with(monkeypatch: pytest.MonkeyPatch):
    def apply(*responses: Response) -> Recorder:
        recorder = Recorder(*responses)
        monkeypatch.setattr(
            synthesizer,
            "get_client",
            lambda: type("C", (), {"messages": recorder})(),
        )
        return recorder

    return apply


@pytest.fixture
def fail_with(monkeypatch: pytest.MonkeyPatch):
    def apply(exc: Exception):
        async def create(**_: Any) -> Response:
            raise exc

        monkeypatch.setattr(
            synthesizer,
            "get_client",
            lambda: type("C", (), {"messages": type("M", (), {"create": staticmethod(create)})()})(),
        )

    return apply


# --- fixtures ---------------------------------------------------------------


def plan_with(*names: str) -> QueryPlan:
    return QueryPlan(
        query="How is NVIDIA doing?",
        tool_calls=[
            PlannedToolCall(id=f"toolu_{i}", name=name, arguments={"tickers": ["NVDA"]})
            for i, name in enumerate(names)
        ],
        model="claude-sonnet-5",
    )


def execution_with(*results: ToolResult) -> ExecutionResult:
    return ExecutionResult(results=list(results))


def ok_result(tool_use_id: str, name: str, data: Any) -> ToolResult:
    return ToolResult(tool_use_id=tool_use_id, name=name, ok=True, data=data)


def failed_result(tool_use_id: str, name: str, error: str) -> ToolResult:
    return ToolResult(tool_use_id=tool_use_id, name=name, ok=False, error=error)


VALID_PAYLOAD: dict[str, Any] = {
    "summary": "NVIDIA is trading near its high on strong data centre demand.",
    "sections": [
        {
            "title": "Headline figures",
            "type": "company_card",
            "content": {
                "ticker": "NVDA",
                "company_name": "NVIDIA Corporation",
                "metrics": [{"label": "P/E", "value": "62.1"}],
            },
            "confidence": "high",
            "sources": [
                {"type": "api", "label": "yfinance", "data_as_of": "2026-07-27T10:00:00Z"}
            ],
        }
    ],
}


# --- the happy path ---------------------------------------------------------


async def test_valid_output_becomes_a_report(respond_with) -> None:
    respond_with(Response([emit(VALID_PAYLOAD)]))

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {"snapshots": {}})),
    )

    assert report.summary.startswith("NVIDIA is trading")
    assert len(report.sections) == 1
    assert isinstance(report.sections[0].content, CompanyCardContent)
    assert report.sections[0].content.ticker == "NVDA"
    assert report.sections[0].sources[0].label == "yfinance"


async def test_generated_at_is_set_by_the_backend(respond_with) -> None:
    """The model is never asked for the timestamp, so it is always present."""
    respond_with(Response([emit(VALID_PAYLOAD)]))

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.generated_at is not None


@pytest.mark.parametrize(
    ("section_type", "content", "expected"),
    [
        ("text", {"text": "Risks are elevated."}, TextContent),
        ("table", {"columns": ["Metric", "NVDA"], "rows": [["P/E", "62.1"]]}, TableContent),
        (
            "chart",
            {"series": [{"label": "NVDA", "points": [{"date": "2026-07-01", "value": 812.4}]}]},
            ChartContent,
        ),
        ("company_card", {"ticker": "NVDA", "metrics": []}, CompanyCardContent),
        (
            "sentiment",
            {"overall": "positive", "items": [{"headline": "Beat", "sentiment": "positive"}]},
            SentimentContent,
        ),
    ],
)
async def test_each_section_type_parses_to_its_own_model(
    respond_with, section_type: str, content: dict[str, Any], expected: type
) -> None:
    respond_with(
        Response(
            [
                emit(
                    {
                        "summary": "s",
                        "sections": [
                            {
                                "title": "T",
                                "type": section_type,
                                "content": content,
                                "confidence": "medium",
                                "sources": [],
                            }
                        ],
                    }
                )
            ]
        )
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert isinstance(report.sections[0].content, expected)


async def test_text_content_survives_as_a_bare_string(respond_with) -> None:
    """Models commonly send content as a plain string; accepting it avoids a retry."""
    respond_with(
        Response(
            [
                emit(
                    {
                        "summary": "s",
                        "sections": [
                            {
                                "title": "Risks",
                                "type": "text",
                                "content": "Supply concentration is the main risk.",
                                "confidence": "low",
                                "sources": [],
                            }
                        ],
                    }
                )
            ]
        )
    )

    report = await synthesizer.synthesize(
        plan_with("search_knowledge_base"),
        execution_with(ok_result("toolu_0", "search_knowledge_base", {})),
    )

    assert report.sections[0].content == TextContent(text="Supply concentration is the main risk.")


async def test_ragged_table_rows_are_padded_not_rejected(respond_with) -> None:
    respond_with(
        Response(
            [
                emit(
                    {
                        "summary": "s",
                        "sections": [
                            {
                                "title": "Comparison",
                                "type": "table",
                                "content": {
                                    "columns": ["Metric", "NVDA", "AMD"],
                                    "rows": [["P/E", "62.1"], ["EPS", "2.1", "0.9", "extra"]],
                                },
                                "confidence": "high",
                                "sources": [],
                            }
                        ],
                    }
                )
            ]
        )
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    content = report.sections[0].content
    assert isinstance(content, TableContent)
    assert content.rows == [["P/E", "62.1", None], ["EPS", "2.1", "0.9"]]


# --- degradation flags are the backend's, not the model's --------------------


async def test_failed_tools_come_from_execution_not_the_model(respond_with) -> None:
    """The model cannot talk the report out of being partial."""
    lying = {**VALID_PAYLOAD, "partial": False, "failed_tools": []}
    respond_with(Response([emit(lying)]))

    report = await synthesizer.synthesize(
        plan_with("get_market_data", "get_news_sentiment"),
        execution_with(
            ok_result("toolu_0", "get_market_data", {}),
            failed_result("toolu_1", "get_news_sentiment", "timed out after 25.0s"),
        ),
    )

    assert report.partial is True
    assert report.failed_tools == ["get_news_sentiment"]


async def test_a_report_built_on_nothing_is_still_partial(respond_with) -> None:
    """Every tool failing is more degraded than some failing, not less."""
    respond_with(Response([emit(VALID_PAYLOAD)]))

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(failed_result("toolu_0", "get_market_data", "provider down")),
    )

    assert report.partial is True
    assert report.failed_tools == ["get_market_data"]


async def test_a_clean_run_is_not_partial(respond_with) -> None:
    respond_with(Response([emit(VALID_PAYLOAD)]))

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.partial is False
    assert report.failed_tools == []


# --- what the model is shown ------------------------------------------------


async def test_tool_failures_are_shown_to_the_model(respond_with) -> None:
    """A failed tool must reach the model so the report can admit the gap."""
    recorder = respond_with(Response([emit(VALID_PAYLOAD)]))

    await synthesizer.synthesize(
        plan_with("get_news_sentiment"),
        execution_with(failed_result("toolu_0", "get_news_sentiment", "rate limited")),
    )

    results = recorder.calls[0]["messages"][2]["content"]
    assert results[0]["is_error"] is True
    assert "rate limited" in results[0]["content"]


async def test_every_tool_call_gets_a_result_block(respond_with) -> None:
    """An unanswered tool_use is a 400 from the API, so gaps are filled in."""
    recorder = respond_with(Response([emit(VALID_PAYLOAD)]))

    await synthesizer.synthesize(
        plan_with("get_market_data", "get_news_sentiment"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),  # toolu_1 missing
    )

    sent = recorder.calls[0]["messages"]
    used = [b["id"] for b in sent[1]["content"]]
    answered = [b["tool_use_id"] for b in sent[2]["content"]]
    assert used == answered == ["toolu_0", "toolu_1"]
    assert sent[2]["content"][1]["is_error"] is True


async def test_output_is_forced_through_the_emit_tool(respond_with) -> None:
    recorder = respond_with(Response([emit(VALID_PAYLOAD)]))

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    call = recorder.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": synthesizer.EMIT_REPORT}
    assert [t["name"] for t in call["tools"]] == [synthesizer.EMIT_REPORT]


async def test_oversized_results_are_truncated(respond_with) -> None:
    recorder = respond_with(Response([emit(VALID_PAYLOAD)]))
    bulky = {"points": [{"date": "2026-01-01", "value": i} for i in range(20_000)]}
    assert len(json.dumps(bulky)) > synthesizer.MAX_TOOL_RESULT_CHARS

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", bulky)),
    )

    sent = recorder.calls[0]["messages"][2]["content"][0]["content"]
    assert "truncated" in sent
    assert len(sent) < synthesizer.MAX_TOOL_RESULT_CHARS + 200


# --- retry ------------------------------------------------------------------


async def test_malformed_output_is_retried_once_and_can_succeed(respond_with) -> None:
    recorder = respond_with(
        Response([emit({"summary": "s", "sections": [{"title": "T"}]})]),  # invalid section
        Response([emit(VALID_PAYLOAD)]),
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.summary.startswith("NVIDIA is trading")
    assert len(recorder.calls) == 2


async def test_the_retry_shows_the_model_its_own_errors(respond_with) -> None:
    recorder = respond_with(
        Response([emit({"summary": "s", "sections": [{"title": "T"}]})]),
        Response([emit(VALID_PAYLOAD)]),
    )

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    feedback = recorder.calls[1]["messages"][-1]["content"][0]
    assert feedback["is_error"] is True
    assert "rejected" in feedback["content"]


async def test_two_malformed_outputs_raise(respond_with) -> None:
    recorder = respond_with(
        Response([emit({"sections": []})]),
        Response([emit({"sections": []})]),
    )

    with pytest.raises(UpstreamUnavailable, match="failed validation twice"):
        await synthesizer.synthesize(
            plan_with("get_market_data"),
            execution_with(ok_result("toolu_0", "get_market_data", {})),
        )

    assert len(recorder.calls) == 2


async def test_a_missing_tool_call_is_treated_as_malformed(respond_with) -> None:
    recorder = respond_with(
        Response([Block("text", text="Here is the report:")]),
        Response([emit(VALID_PAYLOAD)]),
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.summary.startswith("NVIDIA is trading")
    assert len(recorder.calls) == 2


async def test_provider_errors_are_translated(fail_with) -> None:
    import anthropic
    import httpx

    fail_with(anthropic.APITimeoutError(request=httpx.Request("POST", "https://api.anthropic.com")))

    # Timeouts keep their own class all the way to the route, where they become
    # a 504 rather than a generic 502.
    with pytest.raises(UpstreamTimeout) as exc:
        await synthesizer.synthesize(
            plan_with("get_market_data"),
            execution_with(ok_result("toolu_0", "get_market_data", {})),
        )
    assert "anthropic" in str(exc.value)


# --- the zero-tool path -----------------------------------------------------


async def test_a_direct_answer_needs_no_second_call(respond_with) -> None:
    """"What is a P/E ratio?" was already answered; re-asking would waste a call."""
    recorder = respond_with()  # any call at all would raise

    plan = QueryPlan(
        query="What is a P/E ratio?",
        tool_calls=[],
        direct_answer="Price divided by earnings per share.",
        model="claude-sonnet-5",
    )
    report = await synthesizer.synthesize(plan, ExecutionResult())

    assert recorder.calls == []
    assert report.summary == "Price divided by earnings per share."
    assert report.sections[0].content == TextContent(text="Price divided by earnings per share.")
    assert report.partial is False


async def test_a_direct_answer_still_matches_the_contract(respond_with) -> None:
    """The frontend must not be able to tell how a report was produced."""
    respond_with()

    plan = QueryPlan(
        query="What is a P/E ratio?",
        tool_calls=[],
        direct_answer="Price over earnings.",
        model="claude-sonnet-5",
    )
    report = await synthesizer.synthesize(plan, ExecutionResult())

    dumped = report.model_dump(mode="json")
    assert set(dumped) == {
        "summary",
        "sections",
        "partial",
        "failed_tools",
        "generated_at",
    }
    assert dumped["sections"][0]["confidence"] == "high"
    assert dumped["sections"][0]["sources"] == []


async def test_an_empty_direct_answer_yields_no_sections(respond_with) -> None:
    respond_with()

    plan = QueryPlan(query="?", tool_calls=[], direct_answer=None, model="claude-sonnet-5")
    report = await synthesizer.synthesize(plan, ExecutionResult())

    assert report.sections == []
    assert report.summary == ""


# --- against the real model -------------------------------------------------


@pytest.mark.integration
async def test_live_synthesis_conforms_to_the_schema(settings) -> None:
    """Proves the API accepts OUTPUT_TOOL and the model can satisfy it.

    The stubbed tests above validate our parsing; only this one validates the
    tool schema itself, which no amount of mocking can check. Needs a funded
    ANTHROPIC_API_KEY; skips otherwise.
    """
    if not settings.anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY is not configured")

    plan = QueryPlan(
        query="How is NVIDIA performing, and what does recent coverage say?",
        tool_calls=[
            PlannedToolCall(id="toolu_0", name="get_market_data", arguments={"tickers": ["NVDA"]}),
            PlannedToolCall(
                id="toolu_1", name="get_news_sentiment", arguments={"tickers": ["NVDA"]}
            ),
        ],
        model="claude-sonnet-5",
    )
    execution = execution_with(
        ok_result(
            "toolu_0",
            "get_market_data",
            {
                "snapshots": {
                    "NVDA": {
                        "ticker": "NVDA",
                        "company_name": "NVIDIA Corporation",
                        "price": 812.4,
                        "pe_ratio": 62.1,
                        "market_cap": 2_010_000_000_000,
                        "data_as_of": "2026-07-27T10:00:00Z",
                        "source": "yfinance",
                    }
                }
            },
        ),
        failed_result("toolu_1", "get_news_sentiment", "rate limited"),
    )

    try:
        report = await synthesizer.synthesize(plan, execution)
    except UpstreamUnavailable as exc:
        if "credit balance" in str(exc):
            pytest.skip("Anthropic account has no credit")
        raise

    assert report.summary
    assert report.sections
    # The backend's own flags, regardless of what the model wrote.
    assert report.partial is True
    assert report.failed_tools == ["get_news_sentiment"]
