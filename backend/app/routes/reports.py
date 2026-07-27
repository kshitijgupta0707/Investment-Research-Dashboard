"""Saved report endpoints.

Read is organization-wide; update and delete are creator-or-admin. The
permission checks live in the service alongside the row load, because ownership
cannot be resolved before the row is fetched.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app import db
from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.envelope import Envelope, ok
from app.schemas.reports import (
    ReportCreate,
    ReportDetail,
    ReportPage,
    ReportTagsUpdate,
)
from app.services import reports as reports_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=Envelope[ReportDetail], status_code=status.HTTP_201_CREATED)
async def create_report(
    body: ReportCreate,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[ReportDetail]:
    """Save a research result to the shared workspace."""
    return ok(await reports_service.create_report(db.get_pool(), user, body))


@router.get("", response_model=Envelope[ReportPage])
async def list_reports(
    tag: str | None = Query(default=None, description="Exact tag match, case-insensitive."),
    q: str | None = Query(default=None, description="Full-text search over the query text."),
    limit: int = Query(default=20, ge=1, le=reports_service.MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[ReportPage]:
    """List the organization's saved reports, newest first."""
    page = await reports_service.list_reports(
        db.get_pool(), user, tag=tag, search=q, limit=limit, offset=offset
    )
    return ok(page)


@router.get("/{report_id}", response_model=Envelope[ReportDetail])
async def get_report(
    report_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[ReportDetail]:
    """Read one saved report, including its full structured result."""
    return ok(await reports_service.get_report(db.get_pool(), user, report_id))


@router.patch("/{report_id}", response_model=Envelope[ReportDetail])
async def update_report_tags(
    report_id: UUID,
    body: ReportTagsUpdate,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[ReportDetail]:
    """Replace a report's tags. Creator or admin only."""
    report = await reports_service.update_report_tags(db.get_pool(), user, report_id, body.tags)
    return ok(report)


@router.delete("/{report_id}", response_model=Envelope[dict[str, str]])
async def delete_report(
    report_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict[str, str]]:
    """Delete a report. Creator or admin only.

    Returns 200 with the envelope rather than a bodyless 204: the frontend has
    one parse path for every response, and a 204 would be the single case it had
    to special-case.
    """
    await reports_service.delete_report(db.get_pool(), user, report_id)
    return ok({"id": str(report_id), "deleted": "true"})
