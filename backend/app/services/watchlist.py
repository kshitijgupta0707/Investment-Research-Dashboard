"""Watchlist add / list / remove.

One access rule, and it is narrower than the one for reports: a watchlist
belongs to the analyst who built it, not to the organization. There is no
creator-or-admin branch here because there is no shared row to arbitrate --
`org_id` **and** `user_id` are in the WHERE clause, so a colleague's entry is
already invisible by the time any permission question could be asked.
"""

from __future__ import annotations

import logging
from uuid import UUID

import asyncpg
from fastapi import HTTPException, status

from app.models import audit, watchlist
from app.schemas.auth import CurrentUser
from app.schemas.watchlist import WatchlistAdd, WatchlistEntry

logger = logging.getLogger(__name__)

ACTION_ADDED = "watchlist.added"
ACTION_REMOVED = "watchlist.removed"


async def add_entry(
    pool: asyncpg.Pool, user: CurrentUser, payload: WatchlistAdd
) -> tuple[WatchlistEntry, bool]:
    """Pin a company. Returns the entry and whether it was newly created."""
    row, created = await watchlist.add(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        ticker=payload.ticker,
        company_name=payload.company_name,
    )
    entry = WatchlistEntry.model_validate(dict(row))

    # Re-adding something already pinned changed nothing, so there is nothing to
    # record. An audit trail of no-ops is noise that hides the real entries.
    if created:
        await audit.record(
            pool,
            org_id=user.org_id,
            user_id=user.id,
            action=ACTION_ADDED,
            entity_type="watchlist",
            entity_id=entry.id,
            metadata={"ticker": entry.ticker},
        )
        logger.info("watchlist entry added", extra={"context": {"ticker": entry.ticker}})

    return entry, created


async def list_entries(pool: asyncpg.Pool, user: CurrentUser) -> list[WatchlistEntry]:
    """The caller's own pinned companies.

    Unpaginated by design -- a watchlist that needs a second page is not a
    watchlist -- so the response is a plain list rather than a page envelope.
    """
    rows = await watchlist.list_for_user(pool, user.org_id, user.id)
    return [WatchlistEntry.model_validate(dict(row)) for row in rows]


async def remove_entry(pool: asyncpg.Pool, user: CurrentUser, entry_id: UUID) -> None:
    """Unpin a company. Another user's id is a 404, not a 403."""
    if not await watchlist.delete(pool, user.org_id, user.id, entry_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Watchlist entry not found.",
        )

    await audit.record(
        pool,
        org_id=user.org_id,
        user_id=user.id,
        action=ACTION_REMOVED,
        entity_type="watchlist",
        entity_id=entry_id,
    )
