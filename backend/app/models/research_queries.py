"""Accessors for `research_queries` -- the query history.

Every query is recorded, including ones that failed and ones the analyst never
saved as a report. `tools_selected` is the durable evidence that the agent
chooses tools per query rather than following a fixed path, so it is written
even when the run went on to fail.

Reading this back is CR-16.
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
