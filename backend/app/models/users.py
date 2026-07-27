"""Accessors for the `users` table."""

from __future__ import annotations

from uuid import UUID

import asyncpg


async def get_by_auth_id(pool: asyncpg.Pool, auth_id: UUID) -> asyncpg.Record | None:
    """Look up the application user behind a Supabase Auth id."""
    return await pool.fetchrow(
        """
        select id, supabase_auth_id, email, name, org_id, role
        from users
        where supabase_auth_id = $1
        """,
        auth_id,
    )
