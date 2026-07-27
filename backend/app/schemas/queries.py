"""Response models for query history."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.research_queries import QueryStatus


class QueryHistoryEntry(BaseModel):
    """One past query, saved as a report or not.

    `tools_selected` is carried through to the client because it is the visible
    evidence that the agent picks tools per query: two adjacent rows in the same
    history show different tool sets for different questions.
    """

    id: UUID
    query_text: str
    tools_selected: list[str]
    status: QueryStatus
    latency_ms: int | None
    created_at: datetime


class QueryHistoryPage(BaseModel):
    """`total` is the count before pagination, matching `ReportPage`."""

    items: list[QueryHistoryEntry]
    total: int
    limit: int
    offset: int
