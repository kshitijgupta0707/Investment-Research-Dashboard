"""Reading back query history.

Write-side lives in `services.research`, which records every run including the
ones that failed. This module only reads, so there is nothing to audit: a user
looking at their own history is not an event worth a row in the audit trail.
"""

from __future__ import annotations

import asyncpg

from app.models import research_queries
from app.schemas.auth import CurrentUser
from app.schemas.queries import QueryHistoryEntry, QueryHistoryPage

MAX_PAGE_SIZE = 100


async def list_history(
    pool: asyncpg.Pool,
    user: CurrentUser,
    *,
    limit: int = 20,
    offset: int = 0,
) -> QueryHistoryPage:
    """The caller's own past queries, newest first."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    rows, total = await research_queries.list_for_user(
        pool, user.org_id, user.id, limit=limit, offset=offset
    )
    return QueryHistoryPage(
        items=[QueryHistoryEntry.model_validate(dict(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
