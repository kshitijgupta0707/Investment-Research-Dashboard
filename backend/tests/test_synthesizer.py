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
from google.genai import types

from app.agent import client as agent_client
from app.agent import synthesizer
from app.integrations.errors import UpstreamRateLimited, UpstreamTimeout, UpstreamUnavailable
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


# Built from the real SDK types, so these fail if the shape the synthesizer
# reads stops matching what the SDK returns.


def a_response(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=list(parts)),
                finish_reason=types.FinishReason.STOP,
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=500, candidates_token_count=300
        ),
        model_version="gemini-2.5-flash",
    )


def emit(payload: dict[str, Any]) -> types.GenerateContentResponse:
    """A response whose only content is the forced emit_report call."""
    return a_response(
        types.Part.from_function_call(name=synthesizer.EMIT_REPORT, args=payload)
    )


def no_call() -> types.GenerateContentResponse:
    """The model answered in prose instead of calling the tool."""
    return a_response(types.Part.from_text(text="Here is the report you asked for."))


class Recorder:
    """Serves canned responses in order and keeps the requests that produced them."""

    def __init__(self, *responses: types.GenerateContentResponse) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> types.GenerateContentResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("model called more times than the test allows")
        return self.responses.pop(0)


def _stub_client(monkeypatch: pytest.MonkeyPatch, models: Any) -> None:
    aio = type("Aio", (), {"models": models})()
    # Patched on `agent.client`: model calls go through `client.generate`, which
    # resolves `get_client` in its own module namespace.
    monkeypatch.setattr(
        agent_client, "get_client", lambda: type("Client", (), {"aio": aio})()
    )


@pytest.fixture
def respond_with(monkeypatch: pytest.MonkeyPatch):
    def apply(*responses: types.GenerateContentResponse) -> Recorder:
        recorder = Recorder(*responses)
        _stub_client(monkeypatch, recorder)
        return recorder

    return apply


@pytest.fixture
def fail_with(monkeypatch: pytest.MonkeyPatch):
    def apply(exc: Exception):
        async def generate_content(**_: Any) -> types.GenerateContentResponse:
            raise exc

        _stub_client(
            monkeypatch,
            type("Models", (), {"generate_content": staticmethod(generate_content)})(),
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
        model="gemini-2.5-flash",
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
    respond_with(emit(VALID_PAYLOAD))

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
    respond_with(emit(VALID_PAYLOAD))

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
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert isinstance(report.sections[0].content, expected)


async def test_text_content_survives_as_a_bare_string(respond_with) -> None:
    """Models commonly send content as a plain string; accepting it avoids a retry."""
    respond_with(
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
    )

    report = await synthesizer.synthesize(
        plan_with("search_knowledge_base"),
        execution_with(ok_result("toolu_0", "search_knowledge_base", {})),
    )

    assert report.sections[0].content == TextContent(text="Supply concentration is the main risk.")


async def test_ragged_table_rows_are_padded_not_rejected(respond_with) -> None:
    respond_with(
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
    respond_with(emit(lying))

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
    respond_with(emit(VALID_PAYLOAD))

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(failed_result("toolu_0", "get_market_data", "provider down")),
    )

    assert report.partial is True
    assert report.failed_tools == ["get_market_data"]


async def test_a_clean_run_is_not_partial(respond_with) -> None:
    respond_with(emit(VALID_PAYLOAD))

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.partial is False
    assert report.failed_tools == []


# --- what the model is shown ------------------------------------------------
#
# Turn 2 is one user turn of text, not a replayed function-call exchange --
# Gemini requires a thought_signature on any function call handed back to it,
# and these are reconstructed rather than received. These assert on the text.


def _prompt(call: dict[str, Any]) -> str:
    """The text of the first (and only) content block sent."""
    return call["contents"][0].parts[0].text


async def test_the_question_reaches_the_model(respond_with) -> None:
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert "How is NVIDIA doing?" in _prompt(recorder.calls[0])


async def test_no_function_call_is_replayed(respond_with) -> None:
    """A reconstructed call has no thought_signature, which Gemini 3 rejects."""
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    parts = [p for c in recorder.calls[0]["contents"] for p in c.parts]
    assert all(p.function_call is None for p in parts)
    assert all(p.function_response is None for p in parts)


async def test_tool_failures_are_shown_to_the_model(respond_with) -> None:
    """A failed tool must reach the model so the report can admit the gap."""
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_news_sentiment"),
        execution_with(failed_result("toolu_0", "get_news_sentiment", "rate limited")),
    )

    prompt = _prompt(recorder.calls[0])
    assert "get_news_sentiment" in prompt
    assert "rate limited" in prompt
    assert "failed" in prompt.lower(), "a failure must not read as an empty result"


async def test_a_successful_result_reaches_the_model(respond_with) -> None:
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {"pe": 62.1})),
    )

    assert "62.1" in _prompt(recorder.calls[0])


async def test_every_tool_call_is_accounted_for(respond_with) -> None:
    """Silence about an unrun tool would read as 'it returned nothing'."""
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_market_data", "get_news_sentiment"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),  # toolu_1 missing
    )

    prompt = _prompt(recorder.calls[0])
    assert "get_market_data" in prompt and "get_news_sentiment" in prompt
    assert "did not run" in prompt


async def test_output_is_forced_through_the_emit_tool(respond_with) -> None:
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    config = recorder.calls[0]["config"]
    calling = config.tool_config.function_calling_config

    # ANY plus a single allowed name is what removes the prose option.
    assert calling.mode == types.FunctionCallingConfigMode.ANY
    assert calling.allowed_function_names == [synthesizer.EMIT_REPORT]
    declared = [d.name for tool in config.tools for d in tool.function_declarations]
    assert declared == [synthesizer.EMIT_REPORT]


async def test_the_sdk_does_not_invoke_tools_itself(respond_with) -> None:
    """We run tools ourselves; the SDK's own loop would try to call schemas."""
    recorder = respond_with(emit(VALID_PAYLOAD))

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert recorder.calls[0]["config"].automatic_function_calling.disable is True


async def test_oversized_results_are_truncated(respond_with) -> None:
    recorder = respond_with(emit(VALID_PAYLOAD))
    bulky = {"points": [{"date": "2026-01-01", "value": i} for i in range(20_000)]}
    assert len(json.dumps(bulky)) > synthesizer.MAX_TOOL_RESULT_CHARS

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", bulky)),
    )

    sent = _prompt(recorder.calls[0])
    assert "truncated" in sent
    assert len(sent) < synthesizer.MAX_TOOL_RESULT_CHARS + 500


# --- retry ------------------------------------------------------------------


async def test_malformed_output_is_retried_once_and_can_succeed(respond_with) -> None:
    recorder = respond_with(
        emit({"summary": "s", "sections": [{"title": "T"}]}),  # invalid section
        emit(VALID_PAYLOAD),
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.summary.startswith("NVIDIA is trading")
    assert len(recorder.calls) == 2


async def test_the_retry_shows_the_model_its_own_errors(respond_with) -> None:
    recorder = respond_with(
        emit({"summary": "s", "sections": [{"title": "T"}]}),
        emit(VALID_PAYLOAD),
    )

    await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    # The retry continues the same exchange: the model is shown its own
    # rejected output alongside the validation errors.
    feedback = recorder.calls[1]["contents"][-1].parts[0].text

    assert "rejected" in feedback
    assert "<validation_errors>" in feedback
    assert "sections" in feedback, "the model should see what it actually sent"


async def test_two_malformed_outputs_raise(respond_with) -> None:
    recorder = respond_with(
        emit({"sections": []}),
        emit({"sections": []}),
    )

    with pytest.raises(UpstreamUnavailable, match="failed validation twice"):
        await synthesizer.synthesize(
            plan_with("get_market_data"),
            execution_with(ok_result("toolu_0", "get_market_data", {})),
        )

    assert len(recorder.calls) == 2


async def test_a_missing_tool_call_is_treated_as_malformed(respond_with) -> None:
    recorder = respond_with(
        no_call(),
        emit(VALID_PAYLOAD),
    )

    report = await synthesizer.synthesize(
        plan_with("get_market_data"),
        execution_with(ok_result("toolu_0", "get_market_data", {})),
    )

    assert report.summary.startswith("NVIDIA is trading")
    assert len(recorder.calls) == 2


async def test_provider_errors_are_translated(fail_with) -> None:
    import httpx

    fail_with(httpx.TimeoutException("timed out"))

    # Timeouts keep their own class all the way to the route, where they become
    # a 504 rather than a generic 502.
    with pytest.raises(UpstreamTimeout) as exc:
        await synthesizer.synthesize(
            plan_with("get_market_data"),
            execution_with(ok_result("toolu_0", "get_market_data", {})),
        )
    assert "gemini" in str(exc.value)


# --- the zero-tool path -----------------------------------------------------


async def test_a_direct_answer_needs_no_second_call(respond_with) -> None:
    """"What is a P/E ratio?" was already answered; re-asking would waste a call."""
    recorder = respond_with()  # any call at all would raise

    plan = QueryPlan(
        query="What is a P/E ratio?",
        tool_calls=[],
        direct_answer="Price divided by earnings per share.",
        model="gemini-2.5-flash",
    )
    report = await synthesizer.synthesize(plan, ExecutionResult())

    assert recorder.calls == []
    assert report.summary == ""
    assert report.sections[0].content == TextContent(text="Price divided by earnings per share.")
    assert report.partial is False


async def test_a_direct_answer_still_matches_the_contract(respond_with) -> None:
    """The frontend must not be able to tell how a report was produced."""
    respond_with()

    plan = QueryPlan(
        query="What is a P/E ratio?",
        tool_calls=[],
        direct_answer="Price over earnings.",
        model="gemini-2.5-flash",
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

    plan = QueryPlan(query="?", tool_calls=[], direct_answer=None, model="gemini-2.5-flash")
    report = await synthesizer.synthesize(plan, ExecutionResult())

    assert report.sections == []
    assert report.summary == ""


# --- against the real model -------------------------------------------------


@pytest.mark.integration
async def test_live_synthesis_conforms_to_the_schema(settings) -> None:
    """Proves the API accepts OUTPUT_TOOL and the model can satisfy it.

    The stubbed tests above validate our parsing; only this one validates the
    tool schema itself, which no amount of mocking can check. Needs a working
    GEMINI_API_KEY; skips otherwise.
    """
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not configured")

    plan = QueryPlan(
        query="How is NVIDIA performing, and what does recent coverage say?",
        tool_calls=[
            PlannedToolCall(id="toolu_0", name="get_market_data", arguments={"tickers": ["NVDA"]}),
            PlannedToolCall(
                id="toolu_1", name="get_news_sentiment", arguments={"tickers": ["NVDA"]}
            ),
        ],
        model="gemini-2.5-flash",
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
    except UpstreamRateLimited:
        pytest.skip("Gemini free-tier rate limit reached")
    except UpstreamUnavailable as exc:
        if "quota" in str(exc).lower():
            pytest.skip("Gemini quota exhausted")
        raise

    assert report.summary
    assert report.sections
    # The backend's own flags, regardless of what the model wrote.
    assert report.partial is True
    assert report.failed_tools == ["get_news_sentiment"]
