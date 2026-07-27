"""Role and ownership guards.

Two different questions, deliberately kept separate:

* `require_admin` -- a route-level dependency. "May this role reach this
  endpoint at all?" Resolved before the handler runs.
* `require_owner_or_admin` -- a per-row check. "May this caller modify *this*
  record?" Cannot be a dependency, because it needs the row loaded first.

Both raise 403. Note that 403 means the caller is known but not permitted; a
record belonging to another organization must return **404**, not 403, so we
never confirm that someone else's id exists.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status

from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser


async def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """Route dependency for admin-only endpoints.

    Chains `get_current_user`, so an unauthenticated caller still gets 401
    rather than 403 -- the token is checked before the role is.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This action requires the admin role.",
        )
    return user


def require_owner_or_admin(user: CurrentUser, created_by: UUID) -> None:
    """Allow a write only if the caller created the record, or is an admin.

    Call this *after* loading the row with an `org_id` filter, so a record from
    another organization has already produced a 404.
    """
    if user.is_admin or user.id == created_by:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the creator of this record or an admin may modify it.",
    )
