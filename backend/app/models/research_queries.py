"""Accessors for `research_queries` -- the query history.

Every query is recorded, including ones that failed and ones the analyst never
saved as a report. `tools_selected` is the durable evidence that the agent
chooses tools per query rather than following a fixed path, so it is written
even when the run went on to fail.

Reads are scoped to **org and user**: history is the analyst's own record of
what they asked, not shared workspace state. That is the same boundary the
`research_queries_own` RLS policy draws.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

import asyncpg

QueryStatus = Literal["success", "partial", "failed"]


async def record(
    pool: asyncpg.Pool,
    *,
    org_id: UUID,
    user_id: UUID,
    query_text: str,
    tools_selected: list[str],
    status: QueryStatus,
    latency_ms: int,
) -> UUID:
    """Append one history row and return its id."""
    return await pool.fetchval(
        """
        insert into research_queries
            (org_id, user_id, query_text, tools_selected, status, latency_ms)
        values ($1, $2, $3, $4, $5, $6)
        returning id
        """,
        org_id,
        user_id,
        query_text,
        tools_selected,
        status,
        latency_ms,
    )


async def list_for_user(
    pool: asyncpg.Pool,
    org_id: UUID,
    user_id: UUID,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """One user's history, newest first, plus the pre-pagination total.

    The `(org_id, user_id, created_at desc)` index covers both the filter and
    the sort, so the dashboard widget's read is an index scan rather than a sort
    over the org's whole history.
    """
    total = await pool.fetchval(
        "select count(*) from research_queries where org_id = $1 and user_id = $2",
        org_id,
        user_id,
    )

    rows = await pool.fetch(
        """
        select id, query_text, tools_selected, status, latency_ms, created_at
        from research_queries
        where org_id = $1 and user_id = $2
        order by created_at desc, id desc
        limit $3 offset $4
        """,
        org_id,
        user_id,
        limit,
        offset,
    )
    return list(rows), int(total or 0)
