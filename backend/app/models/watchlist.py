"""Accessors for `watchlist`.

Scoped to **org and user**, not just org. A watchlist is one analyst's set of
pinned companies rather than shared workspace state, which is the same boundary
the `watchlist_own` RLS policy draws. Both columns appear in every WHERE clause
here, so another member's entry is indistinguishable from one that never
existed -- and so a foreign id answers 404 rather than 403.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

_COLUMNS = "id, ticker, company_name, created_at"


async def add(
    pool: asyncpg.Pool,
    *,
    org_id: UUID,
    user_id: UUID,
    ticker: str,
    company_name: str | None,
) -> tuple[asyncpg.Record, bool]:
    """Pin a ticker. Returns the row and whether this call created it.

    Adding a ticker already on the list is a no-op rather than an error: the
    only way a user triggers it is by pressing a button whose outcome they
    already wanted, and `on conflict do nothing` keeps that from turning into a
    unique-violation 500. The second fetch runs only on that path.
    """
    row = await pool.fetchrow(
        f"""
        insert into watchlist (org_id, user_id, ticker, company_name)
        values ($1, $2, $3, $4)
        on conflict (org_id, user_id, ticker) do nothing
        returning {_COLUMNS}
        """,
        org_id,
        user_id,
        ticker,
        company_name,
    )
    if row is not None:
        return row, True

    existing = await pool.fetchrow(
        f"""
        select {_COLUMNS}
        from watchlist
        where org_id = $1 and user_id = $2 and ticker = $3
        """,
        org_id,
        user_id,
        ticker,
    )
    return existing, False


async def list_for_user(pool: asyncpg.Pool, org_id: UUID, user_id: UUID) -> list[asyncpg.Record]:
    """One user's pinned companies, alphabetically.

    Ordered by ticker rather than by recency: a watchlist is scanned for a known
    symbol, and insertion order would reshuffle the list under the reader every
    time they added one.
    """
    rows = await pool.fetch(
        f"""
        select {_COLUMNS}
        from watchlist
        where org_id = $1 and user_id = $2
        order by ticker asc
        """,
        org_id,
        user_id,
    )
    return list(rows)


async def delete(pool: asyncpg.Pool, org_id: UUID, user_id: UUID, entry_id: UUID) -> bool:
    """True if a row was removed. False means absent, or somebody else's."""
    result = await pool.execute(
        "delete from watchlist where id = $1 and org_id = $2 and user_id = $3",
        entry_id,
        org_id,
        user_id,
    )
    return result.endswith(" 1")
