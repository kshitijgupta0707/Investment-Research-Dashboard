"""Query history endpoint. Powers the dashboard's recent-queries widget."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app import db
from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.envelope import Envelope, ok
from app.schemas.queries import QueryHistoryPage
from app.services import queries as queries_service

router = APIRouter(prefix="/api/queries", tags=["queries"])


@router.get("", response_model=Envelope[QueryHistoryPage])
async def list_query_history(
    limit: int = Query(default=20, ge=1, le=queries_service.MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[QueryHistoryPage]:
    """The caller's own past queries, newest first, saved or not."""
    page = await queries_service.list_history(db.get_pool(), user, limit=limit, offset=offset)
    return ok(page)
