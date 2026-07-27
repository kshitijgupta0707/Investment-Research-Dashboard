"""Accessors for `organizations` and the membership rows in `users`.

Both provisioning paths -- founding an organization and redeeming an invite --
insert into two tables. Each is written as a **single statement with CTEs** so
that it is atomic without an explicit transaction: an organization with no admin,
or a user row pointing at an organization that was never created, is not a state
worth being able to reach.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg

_MEMBER_COLUMNS = "id, email, name, role, created_at"


async def create_with_admin(
    pool: asyncpg.Pool,
    *,
    name: str,
    auth_id: UUID,
    email: str,
    user_name: str | None,
) -> asyncpg.Record:
    """Found an organization; the caller becomes its admin.

    Raises `asyncpg.UniqueViolationError` if this auth id already has a
    membership -- `users.supabase_auth_id` is unique, which makes the constraint
    the guard against a double signup rather than a read-then-write check that
    two concurrent requests could both pass.
    """
    return await pool.fetchrow(
        """
        with org as (
            insert into organizations (name) values ($1)
            returning id, name
        ), member as (
            insert into users (supabase_auth_id, email, name, org_id, role)
            select $2, $3, $4, org.id, 'admin' from org
            returning id, role
        )
        select org.id as org_id, org.name as org_name,
               member.id as user_id, member.role
        from org, member
        """,
        name,
        auth_id,
        email,
        user_name,
    )


async def join_with_code(
    pool: asyncpg.Pool,
    *,
    code: str,
    auth_id: UUID,
    email: str,
    user_name: str | None,
) -> asyncpg.Record | None:
    """Redeem an invite code, joining as an analyst.

    Returns None if the code does not match a live invite. Validity is decided
    inside the same statement that inserts, so a code revoked between a check
    and a write cannot still be redeemed.

    Expiry is evaluated from `expires_at` rather than from `status`: nothing
    sweeps the table, so a row whose timestamp has passed is still marked
    'active' and must be rejected on the timestamp alone.
    """
    return await pool.fetchrow(
        """
        with invite as (
            select org_id from org_invites
            where code = $1
              and status = 'active'
              and (expires_at is null or expires_at > now())
        ), member as (
            insert into users (supabase_auth_id, email, name, org_id, role)
            select $2, $3, $4, invite.org_id, 'analyst' from invite
            returning id, org_id, role
        )
        select member.org_id, o.name as org_name,
               member.id as user_id, member.role
        from member
        join organizations o on o.id = member.org_id
        """,
        code,
        auth_id,
        email,
        user_name,
    )


async def get(pool: asyncpg.Pool, org_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        """
        select o.id, o.name, o.created_at,
               (select count(*) from users u where u.org_id = o.id) as member_count
        from organizations o
        where o.id = $1
        """,
        org_id,
    )


async def list_members(pool: asyncpg.Pool, org_id: UUID) -> list[asyncpg.Record]:
    """Everyone in one organization. Admins first, then oldest first."""
    rows = await pool.fetch(
        f"""
        select {_MEMBER_COLUMNS}
        from users
        where org_id = $1
        order by (role = 'admin') desc, created_at asc
        """,
        org_id,
    )
    return list(rows)
