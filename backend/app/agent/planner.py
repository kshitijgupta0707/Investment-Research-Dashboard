"""Turn 1 -- deciding which data sources a question needs.

The model reads the question and the three tool schemas and chooses. There is
no keyword routing anywhere in this file or any other: "what's the latest news
on Tesla?" must reach the news tool and *not* the market data tool because the
model decided so, not because the code matched a string.

The model may also choose nothing. A question like "what is a P/E ratio?" needs
no company data, and answering it directly is the correct outcome rather than a
failure to route.
"""

from __future__ import annotations

import logging
import time

from google.genai import types
from pydantic import ValidationError

from app.agent.client import finish_reason as _finish_reason
from app.agent.client import generate
from app.agent.client import response_parts as _parts
from app.agent.tools import TOOL_NAMES, TOOL_SCHEMAS, as_tool, parse_tool_input
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

# It first check whether the tool name is valid, 
# then it checks whether the arguments are valid for that tool. 
# If either of these checks fails, it logs a warning and returns None, indicating that the call should be dropped. 
# Otherwise,it returns a PlannedToolCall object with a unique id, the tool name, and the validated arguments.

#call= { "name": "get_market_data","args": { "tickers": ["NVDA"], "metrics": ["pe_ratio", "market_cap"] } }
def _to_planned_call(call: types.FunctionCall, index: int) -> PlannedToolCall | None:
    """Validate one function call, or drop it.

    The model is prompted to follow the schemas but is not bound by them, so a
    malformed call is possible. Dropping one is better than failing the whole
    query: the remaining tools still produce a partial report.

    Gemini does not assign ids to function calls, so one is minted here from the
    call's position. Everything downstream -- the executor, and the synthesis
    turn that pairs each result back to its request -- keys off this id, so it
    only has to be unique within a plan and stable for the life of it.
    """
    name = call.name or ""
    if name not in TOOL_NAMES:
        logger.warning("planner requested unknown tool", extra={"context": {"tool": name}})
        return None

    arguments = dict(call.args) if isinstance(call.args, dict) else {}
    try:
        parse_tool_input(name, arguments)
    except (ValidationError, ValueError) as exc:
        logger.warning(
            "planner produced invalid tool arguments",
            extra={"context": {"tool": name, "error": str(exc)}},
        )
        return None

    return PlannedToolCall(id=f"call_{index}_{name}", name=name, arguments=arguments)


async def plan_query(query: str) -> QueryPlan:
    """Ask the model which tools this question needs."""
    settings = get_settings()
    started = time.perf_counter()

    response = await generate(
        contents=query,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=MAX_TOKENS,
            tools=[as_tool(TOOL_SCHEMAS)],
            # We run the tools ourselves, concurrently, with our own timeouts
            # and degradation. Left on, the SDK would try to invoke them itself
            # and fail -- these are schemas, not callables.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
        purpose="planning",
    )

    tool_calls: list[PlannedToolCall] = []
    text_parts: list[str] = []

    for index, call in enumerate(response.function_calls or []):
        planned = _to_planned_call(call, index)
        if planned is not None:
            tool_calls.append(planned)

    for part in _parts(response):
        if part.text and part.text.strip():
            text_parts.append(part.text.strip())

    # Commentary alongside tool calls belongs to the planner, not the user; the
    # direct answer only matters when nothing was called.
    direct_answer = "\n\n".join(text_parts) if text_parts and not tool_calls else None

    plan = QueryPlan(
        query=query,
        tool_calls=tool_calls,
        direct_answer=direct_answer,
        model=response.model_version or settings.gemini_model,
        stop_reason=_finish_reason(response),
        latency_ms=round((time.perf_counter() - started) * 1000, 2),
    )

    usage = response.usage_metadata
    logger.info(
        "planned query",
        extra={
            "context": {
                "tools_selected": plan.tool_names,
                "answered_directly": not plan.used_tools,
                "planner_latency_ms": plan.latency_ms,
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None),
            }
        },
    )
    return plan
