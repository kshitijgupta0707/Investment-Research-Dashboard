"""Running one research query end to end.

    plan (Turn 1) -> execute tools in parallel -> synthesize (Turn 2)

Nothing here inspects the query text. Which tools run is decided entirely by the
model in Turn 1; this module's job is to sequence the three steps, record what
happened, and let provider failures surface with their own status code.

History is written on **every** path, including failures. A query that died
because Claude was rate limited is exactly the kind a user wants to see in their
history, and `tools_selected` is the evidence that tool choice varies per query.
"""

from __future__ import annotations

import logging
import time
from uuid import UUID

import asyncpg

from app.agent.executor import ToolContext, execute_plan
from app.agent.planner import plan_query
from app.agent.synthesizer import synthesize
from app.models import audit, research_queries
from app.models.research_queries import QueryStatus
from app.schemas.auth import CurrentUser
from app.schemas.research import ResearchQueryResponse

logger = logging.getLogger(__name__)

AUDIT_ACTION = "research.query"


async def _record(
    pool: asyncpg.Pool,
    user: CurrentUser,
    query_text: str,
    tools_selected: list[str],
    status: QueryStatus,
    latency_ms: float,
) -> UUID:
    """Write the history row and its audit entry, returning the history id."""
    query_id = await research_queries.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        query_text=query_text,
        tools_selected=tools_selected,
        status=status,
        latency_ms=int(latency_ms),
    )
    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=AUDIT_ACTION,
        entity_type="research_query",
        entity_id=query_id,
        metadata={
            "tools_selected": tools_selected,
            "status": status,
            "latency_ms": int(latency_ms),
        },
    )
    return query_id


async def run_research_query(
    pool: asyncpg.Pool,
    user: CurrentUser,
    query_text: str,
    ctx: ToolContext | None = None,
) -> ResearchQueryResponse:
    """Plan, execute and synthesize. Raises `UpstreamError` if Claude is down."""
    started = time.perf_counter()
    tools_selected: list[str] = []

    def elapsed() -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    try:
        plan = await plan_query(query_text)
        tools_selected = plan.tool_names

        execution = await execute_plan(plan, ctx or ToolContext(pool=pool))
        report = await synthesize(plan, execution)
    except Exception as exc:
        # The run is already lost; a second failure while recording it must not
        # replace the real reason with a database error.
        try:
            await _record(pool, user, query_text, tools_selected, "failed", elapsed())
        except Exception:
            logger.exception("failed to record a failed query")

        logger.warning(
            "research query failed",
            extra={
                "context": {
                    "tools_selected": tools_selected,
                    "error": str(exc),
                    "latency_ms": elapsed(),
                }
            },
        )
        raise

    status: QueryStatus = "partial" if report.partial else "success"
    latency_ms = elapsed()
    query_id = await _record(pool, user, query_text, tools_selected, status, latency_ms)

    logger.info(
        "research query completed",
        extra={
            "context": {
                "query_id": str(query_id),
                "tools_selected": tools_selected,
                "status": status,
                "failed_tools": report.failed_tools,
                "sections": len(report.sections),
                "total_latency_ms": latency_ms,
            }
        },
    )

    return ResearchQueryResponse(
        query_id=query_id,
        query_text=query_text,
        tools_selected=tools_selected,
        status=status,
        latency_ms=latency_ms,
        report=report,
    )
