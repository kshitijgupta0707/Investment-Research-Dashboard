"""Watchlist endpoints. Scoped to the calling user, not the organization."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app import db
from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.envelope import Envelope, ok
from app.schemas.watchlist import WatchlistAdd, WatchlistEntry
from app.services import watchlist as watchlist_service

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.post("", response_model=Envelope[WatchlistEntry], status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAdd,
    response: Response,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[WatchlistEntry]:
    """Pin a company.

    201 when the entry is new, 200 when it was already pinned. Re-adding is
    deliberately not a 409: nothing is in conflict, the caller's intent is
    already satisfied, and an error would make the UI handle a failure for a
    button press that did exactly what the user wanted.
    """
    entry, created = await watchlist_service.add_entry(db.get_pool(), user, body)
    if not created:
        response.status_code = status.HTTP_200_OK
    return ok(entry)


@router.get("", response_model=Envelope[list[WatchlistEntry]])
async def list_watchlist(
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[list[WatchlistEntry]]:
    """The caller's pinned companies, alphabetically by ticker."""
    return ok(await watchlist_service.list_entries(db.get_pool(), user))


@router.delete("/{entry_id}", response_model=Envelope[dict[str, str]])
async def remove_from_watchlist(
    entry_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> Envelope[dict[str, str]]:
    """Unpin a company.

    Returns the envelope rather than a bodyless 204, matching reports: the
    frontend keeps one parse path for every response.
    """
    await watchlist_service.remove_entry(db.get_pool(), user, entry_id)
    return ok({"id": str(entry_id), "deleted": "true"})
