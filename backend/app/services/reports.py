"""Saved report CRUD.

Two access rules, and they are different from each other:

* **Read is organization-wide.** A workspace is shared, so any member sees
  every report saved in their org. That is what "share a workspace" means here.
* **Write is creator-or-admin.** An analyst cannot edit or delete a colleague's
  report; an admin can, as part of managing the workspace.

Every write goes through the same shape: load the row filtered by `org_id`,
**404 if it is not there**, then check ownership, then act. The order matters --
answering 403 for another organization's id would confirm that the id exists,
which is enough to enumerate a competitor's report ids without ever reading one.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.middleware.rbac import require_owner_or_admin
from app.models import audit, reports
from app.schemas.auth import CurrentUser
from app.schemas.reports import (
    ReportCreate,
    ReportDetail,
    ReportPage,
    ReportSummary,
)

logger = logging.getLogger(__name__)

ACTION_CREATED = "report.created"
ACTION_UPDATED = "report.updated"
ACTION_DELETED = "report.deleted"
ACTION_NOTES_UPDATED = "report.notes_updated"

MAX_PAGE_SIZE = 100


def _not_found() -> HTTPException:
    """The same answer for absent and for another org's -- deliberately."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")


def _detail(row: asyncpg.Record) -> ReportDetail:
    return ReportDetail.model_validate(dict(row))


async def _load_for_write(
    pool: asyncpg.Pool, user: CurrentUser, report_id: UUID
) -> asyncpg.Record:
    """Fetch a report the caller is allowed to modify, or raise 404/403."""
    row = await reports.get(pool, user.org_id, report_id)
    if row is None:
        raise _not_found()
    require_owner_or_admin(user, row["created_by"])
    return row


async def create_report(
    pool: asyncpg.Pool, user: CurrentUser, payload: ReportCreate
) -> ReportDetail:
    """Save a result. Any member of the organization may do this."""
    row = await reports.create(
        pool,
        org_id=user.org_id,
        created_by=user.id,
        query_text=payload.query_text,
        structured_result=payload.structured_result.model_dump(mode="json"),
        tags=payload.tags,
    )
    report = _detail(row)

    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_CREATED,
        entity_type="research_report",
        entity_id=report.id,
        metadata={"tags": report.tags},
    )
    logger.info(
        "report saved",
        extra={"context": {"report_id": str(report.id), "tags": report.tags}},
    )
    return report


async def list_reports(
    pool: asyncpg.Pool,
    user: CurrentUser,
    *,
    tag: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ReportPage:
    """Every report in the caller's organization, newest first."""
    limit = max(1, min(limit, MAX_PAGE_SIZE))
    offset = max(0, offset)

    rows, total = await reports.list_for_org(
        pool, user.org_id, tag=tag, search=search, limit=limit, offset=offset
    )
    return ReportPage(
        items=[ReportSummary.model_validate(dict(row)) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


async def get_report(pool: asyncpg.Pool, user: CurrentUser, report_id: UUID) -> ReportDetail:
    """Read one report. Org-scoped, so another tenant's id is a 404."""
    row = await reports.get(pool, user.org_id, report_id)
    if row is None:
        raise _not_found()
    return _detail(row)


async def update_report_tags(
    pool: asyncpg.Pool, user: CurrentUser, report_id: UUID, tags: list[str]
) -> ReportDetail:
    """Replace a report's tags. Creator or admin only."""
    before: dict[str, Any] = dict(await _load_for_write(pool, user, report_id))

    row = await reports.update_tags(pool, user.org_id, report_id, tags)
    if row is None:
        # Deleted between the load and the update. Rare, but the alternative is
        # a 500 from validating None.
        raise _not_found()
    report = _detail(row)

    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_UPDATED,
        entity_type="research_report",
        entity_id=report.id,
        metadata={"tags_before": list(before["tags"]), "tags_after": report.tags},
    )
    return report


async def update_report_notes(
    pool: asyncpg.Pool, user: CurrentUser, report_id: UUID, notes: str | None
) -> ReportDetail:
    """Replace a report's analyst note. Creator or admin only.

    Same permission rule as tags and delete, for one reason: a note appears
    inside the report and is attributed to whoever wrote it, so allowing any
    member to overwrite a colleague's commentary would make that attribution
    misleading.
    """
    await _load_for_write(pool, user, report_id)

    row = await reports.update_notes(pool, user.org_id, report_id, notes, user.id)
    if row is None:
        raise _not_found()
    report = _detail(row)

    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_NOTES_UPDATED,
        entity_type="research_report",
        entity_id=report.id,
        # The note's text is not recorded: the audit log is org-readable, and a
        # trail that reproduces every draft of a private view is more exposure
        # than the action needs.
        metadata={"cleared": notes is None, "length": len(notes or "")},
    )
    logger.info(
        "report notes updated",
        extra={"context": {"report_id": str(report.id), "cleared": notes is None}},
    )
    return report


async def delete_report(pool: asyncpg.Pool, user: CurrentUser, report_id: UUID) -> None:
    """Remove a report. Creator or admin only."""
    await _load_for_write(pool, user, report_id)

    if not await reports.delete(pool, user.org_id, report_id):
        raise _not_found()

    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_DELETED,
        entity_type="research_report",
        entity_id=report_id,
    )
    logger.info("report deleted", extra={"context": {"report_id": str(report_id)}})
