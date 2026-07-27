"""The research query endpoint.

Thin by design: validate, resolve the caller, delegate. Orchestration lives in
`app/services/research.py`, and provider failures are translated to 429/502/504
by the global handler rather than caught here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app import db
from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.envelope import Envelope, ok
from app.schemas.research import ResearchQueryRequest, ResearchQueryResponse
from app.services import research as research_service

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/query", response_model=Envelope[ResearchQueryResponse])
async def run_query(
    body: ResearchQueryRequest,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[ResearchQueryResponse]:
    """Answer a natural-language research question.

    The agent decides which data tools the question needs; the response carries
    the structured report plus which tools actually ran.
    """
    result = await research_service.run_research_query(db.get_pool(), user, body.query_text)
    return ok(result)
