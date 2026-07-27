"""Accessors for `org_invites`.

Every query filters by `org_id`, so one organization's admin can neither read
nor revoke another's codes. Redemption is the exception -- it looks up by code
alone, because the whole point is that the joiner does not yet know which
organization they are joining. That lookup lives in `models.organizations`,
inside the same statement that creates the membership.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg

_COLUMNS = """
    i.id, i.code, i.status, i.expires_at, i.created_at,
    u.email as created_by_email
"""


async def create(
    pool: asyncpg.Pool,
    *,
    org_id: UUID,
    created_by: UUID,
    code: str,
    expires_at: datetime | None,
) -> asyncpg.Record:
    """Store one invite code.

    Raises `asyncpg.UniqueViolationError` on a code collision; the caller
    retries with a fresh one.
    """
    return await pool.fetchrow(
        f"""
        with inserted as (
            insert into org_invites (org_id, created_by, code, expires_at)
            values ($1, $2, $3, $4)
            returning *
        )
        select {_COLUMNS}
        from inserted i
        join users u on u.id = i.created_by
        """,
        org_id,
        created_by,
        code,
        expires_at,
    )


async def list_for_org(pool: asyncpg.Pool, org_id: UUID) -> list[asyncpg.Record]:
    """One organization's invites, newest first."""
    rows = await pool.fetch(
        f"""
        select {_COLUMNS}
        from org_invites i
        join users u on u.id = i.created_by
        where i.org_id = $1
        order by i.created_at desc, i.id desc
        """,
        org_id,
    )
    return list(rows)


async def revoke(pool: asyncpg.Pool, org_id: UUID, invite_id: UUID) -> asyncpg.Record | None:
    """Withdraw a live invite. None means absent, already revoked, or another org's.

    The `status = 'active'` filter makes this idempotent in the useful direction:
    revoking twice is a 404 rather than a silent success that suggests something
    changed.
    """
    return await pool.fetchrow(
        f"""
        with updated as (
            update org_invites
            set status = 'revoked'
            where id = $1 and org_id = $2 and status = 'active'
            returning *
        )
        select {_COLUMNS}
        from updated i
        join users u on u.id = i.created_by
        """,
        invite_id,
        org_id,
    )
