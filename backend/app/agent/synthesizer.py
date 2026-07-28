"""Turn 2 -- turning tool output into the structured report.

The conversation is replayed to the model the way it actually happened: the
analyst's question, the tool calls the planner chose, and the results those
calls produced. The model then answers by calling one final tool, `emit_report`,
whose arguments *are* the report.

Forcing a tool call rather than asking for JSON in prose is what makes the
output parseable. There is no prose to strip, no code fence to unwrap, and the
model cannot preface the object with an apology.

Failures are shown to the model rather than hidden. A tool that timed out comes
back as an error result, so the report can say a source was unavailable instead
of quietly omitting it and reading as though the data never mattered.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from google.genai import types
from pydantic import ValidationError

from app.agent.client import PROVIDER, get_client, translate_error
from app.integrations.errors import UpstreamUnavailable
from app.agent.tools import as_tool
from app.schemas.agent import QueryPlan
from app.schemas.execution import ExecutionResult, ToolResult
from app.schemas.report import ResearchReport, SynthesisOutput
from app.utils.config import get_settings

logger = logging.getLogger(__name__)

MAX_TOKENS = 8192
EMIT_REPORT = "emit_report"

# A three-month daily history for three tickers serialises to tens of kilobytes
# of numbers the model does not need in full. Truncating one oversized result
# protects the context window; the chart section is built from the summary
# figures rather than every point.
MAX_TOOL_RESULT_CHARS = 24_000

SYSTEM_PROMPT = """\
You are the synthesis step of an equity research assistant. You have the \
analyst's question and the data that was retrieved for it. Write the report by \
calling the emit_report tool exactly once.

Grounding:

- Use only the retrieved data. Do not add figures from memory, and never \
estimate a number that is missing -- omit it instead.
- If a tool failed, say so in the relevant section rather than writing around \
the gap as though nothing is missing.
- Attribute every section. Market figures cite the api source with its \
data_as_of; news claims cite the article by title and url; anything drawn from \
a filing excerpt cites that filing.

Confidence, per section:

- high -- directly supported by retrieved data
- medium -- reasonable inference from it
- low -- the data is thin, stale, conflicting, or the relevant tool failed

Choosing section types:

- table for comparing the same metrics across companies
- company_card for a single company's headline figures
- chart only when a historical price series was actually retrieved
- sentiment when news articles were classified
- text for narrative: risks, competitive positioning, conclusions

Prefer a few substantial sections over many thin ones. Lead with the summary: \
two or three sentences answering the question directly, before any detail.
"""

# The shapes below mirror app/schemas/report.py. They are still not encoded as a
# `oneOf` union -- models follow a flat schema with clear instructions far more
# reliably than a branching one, and the Pydantic layer rejects anything that
# does not conform regardless.
#
# What the schema *does* have to carry is the union of every field any section
# type can use, each marked with the type it belongs to. An `object` with only a
# description and no `properties` comes back from Gemini as `{}` every time: it
# will not invent a shape the schema does not name. None are required, because
# which ones apply depends on the section's own `type`.
_CONTENT_GUIDE = """\
An object whose shape depends on this section's type:
- text: {"text": "..."} -- markdown paragraphs
- table: {"columns": ["Metric", "NVDA", "AMD"], "rows": [["P/E", "62.1", "45.0"]]}
- chart: {"y_label": "Close (USD)", "series": [{"label": "NVDA", \
"points": [{"date": "2026-01-31", "value": 812.4}]}]}
- company_card: {"ticker": "NVDA", "company_name": "NVIDIA Corporation", \
"metrics": [{"label": "Market cap", "value": "$2.1T"}]}
- sentiment: {"overall": "positive", "items": [{"headline": "...", \
"sentiment": "positive", "ticker": "NVDA", "url": "https://..."}]}

Set only the fields belonging to this section's type; leave the rest out.\
"""

_SENTIMENT_VALUES = ["positive", "negative", "neutral"]

_CONTENT_PROPERTIES: dict[str, Any] = {
    "text": {"type": "string", "description": "text sections: markdown paragraphs."},
    "columns": {
        "type": "array",
        "items": {"type": "string"},
        "description": "table sections: column headers, leftmost first.",
    },
    "rows": {
        "type": "array",
        "items": {"type": "array", "items": {"type": "string"}},
        "description": (
            "table sections: one array of pre-formatted cell values per row, in the "
            "same order as columns."
        ),
    },
    "y_label": {"type": "string", "description": "chart sections: y-axis label."},
    "series": {
        "type": "array",
        "description": "chart sections: one entry per line.",
        "items": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "points": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "date": {"type": "string", "description": "ISO-8601 date."},
                            "value": {"type": "number"},
                        },
                        "required": ["date", "value"],
                    },
                },
            },
            "required": ["label", "points"],
        },
    },
    "ticker": {"type": "string", "description": "company_card sections."},
    "company_name": {"type": "string", "description": "company_card sections."},
    "metrics": {
        "type": "array",
        "description": "company_card sections: pre-formatted figures, e.g. '$2.1T'.",
        "items": {
            "type": "object",
            "properties": {"label": {"type": "string"}, "value": {"type": "string"}},
            "required": ["label"],
        },
    },
    "overall": {
        "type": "string",
        "enum": _SENTIMENT_VALUES,
        "description": "sentiment sections: the net reading across the articles.",
    },
    "items": {
        "type": "array",
        "description": "sentiment sections: one entry per classified article.",
        "items": {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "sentiment": {"type": "string", "enum": _SENTIMENT_VALUES},
                "ticker": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["headline", "sentiment"],
        },
    },
}

OUTPUT_TOOL: dict[str, Any] = {
    "name": EMIT_REPORT,
    "description": (
        "Emit the finished research report. Call this exactly once, as your only "
        "output. Every section must carry its own confidence rating and sources."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "summary": {
                "type": "string",
                "description": (
                    "Two to three sentences answering the analyst's question directly. "
                    "No preamble, no restatement of the question."
                ),
            },
            "sections": {
                "type": "array",
                "description": "The report body, in reading order.",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "type": {
                            "type": "string",
                            "enum": ["text", "table", "chart", "company_card", "sentiment"],
                        },
                        "content": {
                            "type": "object",
                            "description": _CONTENT_GUIDE,
                            "properties": _CONTENT_PROPERTIES,
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "How well the retrieved data supports this section.",
                        },
                        "sources": {
                            "type": "array",
                            "description": (
                                "Where this section's claims came from. Never empty unless "
                                "the section is answering from general knowledge."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["api", "article", "filing"],
                                    },
                                    "label": {
                                        "type": "string",
                                        "description": (
                                            "Human-readable: the provider name, the article "
                                            "title, or the filing label."
                                        ),
                                    },
                                    "url": {
                                        "type": "string",
                                        "description": "Article link, or omit if there is none.",
                                    },
                                    "data_as_of": {
                                        "type": "string",
                                        "description": (
                                            "ISO-8601 timestamp the source reported its data "
                                            "as current, when it gave one."
                                        ),
                                    },
                                },
                                "required": ["type", "label"],
                            },
                        },
                    },
                    "required": ["title", "type", "content", "confidence", "sources"],
                },
            },
        },
        "required": ["summary", "sections"],
    },
}


def _serialise(result: ToolResult) -> str:
    """Render one tool's outcome as the text the model reads."""
    if result.failed:
        return f"This tool failed and returned no data. Reason: {result.error}"

    payload = json.dumps(result.data, default=str)
    if len(payload) > MAX_TOOL_RESULT_CHARS:
        payload = (
            payload[:MAX_TOOL_RESULT_CHARS]
            + f"\n\n[truncated at {MAX_TOOL_RESULT_CHARS} characters]"
        )
    return payload


def _render_exchange(plan: QueryPlan, execution: ExecutionResult) -> str:
    """The question and everything retrieved for it, as one block of text.

    Turn 2 is deliberately **not** replayed as a function-call exchange. Gemini
    requires a `thought_signature` on any function call handed back to it, and
    the calls here are reconstructed from the planner's output rather than
    received intact -- the retry below fabricates one outright, which no
    signature could cover. Presenting the same information as text sidesteps a
    field we cannot honestly produce.

    Nothing is lost by it: the model is forced to call `emit_report` regardless,
    so it never needs to believe it made these calls itself. Failures stay
    visible, which is the property that actually matters -- a report should say
    a source was unavailable rather than quietly omit it.
    """
    by_id = {r.tool_use_id: r for r in execution.results}
    blocks = [f"<question>\n{plan.query}\n</question>", "", "<retrieved_data>"]

    for call in plan.tool_calls:
        result = by_id.get(call.id)
        arguments = json.dumps(call.arguments, default=str)
        blocks.append(f"\n## {call.name}({arguments})")
        if result is None:
            # Only reachable through a bug upstream, but silence would read as
            # "this tool returned nothing", which is a different claim.
            blocks.append("This tool did not run.")
        else:
            blocks.append(_serialise(result))

    blocks.append("\n</retrieved_data>")
    return "\n".join(blocks)


def _build_contents(plan: QueryPlan, execution: ExecutionResult) -> list[types.Content]:
    return [
        types.Content(
            role="user", parts=[types.Part.from_text(text=_render_exchange(plan, execution))]
        )
    ]


def _direct_report(plan: QueryPlan, generated_at: datetime) -> ResearchReport:
    """Wrap a no-tools answer in the same contract.

    "What is a P/E ratio?" was already answered during planning. A second call
    to reformat that into one text section would cost latency and tokens for
    nothing, so it is built here -- but it is the identical schema, because the
    frontend must not care how a report was produced.
    """
    answer = (plan.direct_answer or "").strip()
    return ResearchReport(
        summary=answer,
        sections=[
            {
                "title": "Answer",
                "type": "text",
                "content": {"text": answer},
                # No retrieved data backs this, but a definitional answer is not
                # a weakly-supported one. The empty source list is what tells
                # the UI it came from the model rather than a provider.
                "confidence": "high",
                "sources": [],
            }
        ]
        if answer
        else [],
        partial=False,
        failed_tools=[],
        generated_at=generated_at,
    )


def _extract_output(response: Any) -> dict[str, Any] | None:
    """Pull the emit_report arguments out of the response, if it made the call."""
    for call in response.function_calls or []:
        if call.name == EMIT_REPORT:
            return dict(call.args) if isinstance(call.args, dict) else {}
    return None


async def synthesize(plan: QueryPlan, execution: ExecutionResult) -> ResearchReport:
    """Turn the plan and its results into a validated report.

    Retries once on malformed output, handing the model its own validation
    errors. A second failure raises rather than returning a half-built report:
    the frontend's guarantee is that a report either conforms or does not
    arrive.
    """
    generated_at = datetime.now(UTC)

    if not plan.tool_calls:
        return _direct_report(plan, generated_at)

    settings = get_settings()
    started = time.perf_counter()
    contents = _build_contents(plan, execution)
    last_error = ""

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=MAX_TOKENS,
        tools=[as_tool([OUTPUT_TOOL])],
        # ANY plus a single allowed name is what forces the call. Without it the
        # model is free to answer in prose, and there would be nothing to parse.
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode=types.FunctionCallingConfigMode.ANY,
                allowed_function_names=[EMIT_REPORT],
            )
        ),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )

    for attempt in (1, 2):
        try:
            response = await get_client().aio.models.generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            raise translate_error(exc) from exc

        raw = _extract_output(response)
        if raw is not None:
            try:
                output = SynthesisOutput.model_validate(raw)
            except ValidationError as exc:
                last_error = str(exc)
            else:
                report = ResearchReport(
                    summary=output.summary,
                    sections=output.sections,
                    partial=bool(execution.failed_tools),
                    failed_tools=execution.failed_tools,
                    generated_at=generated_at,
                )
                logger.info(
                    "synthesised report",
                    extra={
                        "context": {
                            "sections": len(report.sections),
                            "partial": report.partial,
                            "failed_tools": report.failed_tools,
                            "attempts": attempt,
                            "synthesis_latency_ms": round(
                                (time.perf_counter() - started) * 1000, 2
                            ),
                            "input_tokens": getattr(
                                response.usage_metadata, "prompt_token_count", None
                            ),
                            "output_tokens": getattr(
                                response.usage_metadata, "candidates_token_count", None
                            ),
                        }
                    },
                )
                return report
        else:
            last_error = "the model returned no emit_report call"

        if attempt == 1:
            logger.warning(
                "synthesis output rejected, retrying",
                extra={"context": {"error": last_error[:500]}},
            )
            # Continue the same exchange rather than starting over: the model is
            # shown its own attempt and what was wrong with it. Quoted back as
            # text rather than as a function call, for the signature reason in
            # `_render_exchange`.
            contents = contents + [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                "Your previous emit_report call was rejected.\n\n"
                                f"<rejected_call>\n{json.dumps(raw or {}, default=str)[:4000]}\n"
                                "</rejected_call>\n\n"
                                f"<validation_errors>\n{last_error[:2000]}\n"
                                "</validation_errors>\n\n"
                                "Call emit_report again, corrected. Change only what the "
                                "errors require."
                            )
                        )
                    ],
                )
            ]

    raise UpstreamUnavailable(PROVIDER, f"synthesis output failed validation twice: {last_error}")
