"""Turn 1 -- deciding which data sources a question needs.

Claude reads the question and the three tool schemas and chooses. There is no
keyword routing anywhere in this file or any other: "what's the latest news on
Tesla?" must reach the news tool and *not* the market data tool because the
model decided so, not because the code matched a string.

The model may also choose nothing. A question like "what is a P/E ratio?" needs
no company data, and answering it directly is the correct outcome rather than a
failure to route.
"""

from __future__ import annotations

import logging
import time

import anthropic
from pydantic import ValidationError

from app.agent.client import get_client, translate_error
from app.agent.tools import TOOL_NAMES, TOOL_SCHEMAS, parse_tool_input
from app.schemas.agent import PlannedToolCall, QueryPlan
from app.utils.config import get_settings

logger = logging.getLogger(__name__)

MAX_TOKENS = 4096

SYSTEM_PROMPT = """\
You are the planning step of an equity research assistant.

Given an analyst's question, decide which data sources it needs and call those \
tools. You are not writing the final report -- a later step does that using \
whatever you request here.

How to choose:

- Call only the tools whose data the question actually requires. An unnecessary \
call adds latency and puts irrelevant material into the report.
- Call several tools when the question genuinely spans them, and pass every \
company the question mentions in a single call rather than one call per company.
- If the question can be answered from general knowledge with no \
company-specific data -- explaining what a financial ratio means, for instance \
-- call no tools at all and answer it directly and concisely.
- Resolve company names to ticker symbols yourself: NVIDIA is NVDA, Tesla is \
TSLA, JPMorgan is JPM.
"""


def _to_planned_call(block: anthropic.types.ToolUseBlock) -> PlannedToolCall | None:
    """Validate one tool_use block, or drop it.

    The model is prompted to follow the schemas but is not bound by them, so a
    malformed call is possible. Dropping one is better than failing the whole
    query: the remaining tools still produce a partial report.
    """
    if block.name not in TOOL_NAMES:
        logger.warning("planner requested unknown tool", extra={"context": {"tool": block.name}})
        return None

    arguments = dict(block.input) if isinstance(block.input, dict) else {}
    try:
        parse_tool_input(block.name, arguments)
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "planner produced invalid tool arguments",
            extra={"context": {"tool": block.name, "error": str(exc)}},
        )
        return None

    return PlannedToolCall(id=block.id, name=block.name, arguments=arguments)


async def plan_query(query: str) -> QueryPlan:
    """Ask Claude which tools this question needs."""
    settings = get_settings()
    started = time.perf_counter()

    try:
        response = await get_client().messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=[{"role": "user", "content": query}],
        )
    except Exception as exc:
        raise translate_error(exc) from exc

    tool_calls: list[PlannedToolCall] = []
    text_parts: list[str] = []

    for block in response.content:
        if block.type == "tool_use":
            planned = _to_planned_call(block)
            if planned is not None:
                tool_calls.append(planned)
        elif block.type == "text" and block.text.strip():
            text_parts.append(block.text.strip())

    # Commentary alongside tool calls belongs to the planner, not the user; the
    # direct answer only matters when nothing was called.
    direct_answer = "\n\n".join(text_parts) if text_parts and not tool_calls else None

    plan = QueryPlan(
        query=query,
        tool_calls=tool_calls,
        direct_answer=direct_answer,
        model=response.model,
        stop_reason=response.stop_reason,
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )

    logger.info(
        "planned query",
        extra={
            "context": {
                "tools_selected": plan.tool_names,
                "answered_directly": not plan.used_tools,
                "planner_latency_ms": plan.latency_ms,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        },
    )
    return plan
