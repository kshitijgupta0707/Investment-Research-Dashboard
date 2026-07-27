"""Accessors for `research_reports`.

**Every query here filters by `org_id`.** That filter is the primary tenant
boundary: the API connects with a privileged role that Row-Level Security does
not constrain, so if it is missing from a query, nothing else stops a
cross-tenant read.

It is applied in the WHERE clause rather than checked after fetching, which is
what makes another organization's report indistinguishable from one that does
not exist -- and so what lets the service answer 404 rather than 403.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg

# The list endpoint never selects structured_result; see ReportSummary.
_SUMMARY_COLUMNS = """
    r.id, r.query_text, r.tags, r.created_by, r.created_at, r.updated_at,
    u.email as created_by_email
"""

_DETAIL_COLUMNS = f"{_SUMMARY_COLUMNS}, r.structured_result"


async def create(
    pool: asyncpg.Pool,
    *,
    org_id: UUID,
    created_by: UUID,
    query_text: str,
    structured_result: dict[str, Any],
    tags: list[str],
) -> asyncpg.Record:
    return await pool.fetchrow(
        f"""
        with inserted as (
            insert into research_reports (org_id, created_by, query_text, structured_result, tags)
            values ($1, $2, $3, $4, $5)
            returning *
        )
        select {_DETAIL_COLUMNS}
        from inserted r
        join users u on u.id = r.created_by
        """,
        org_id,
        created_by,
        query_text,
        structured_result,
        tags,
    )


async def get(pool: asyncpg.Pool, org_id: UUID, report_id: UUID) -> asyncpg.Record | None:
    return await pool.fetchrow(
        f"""
        select {_DETAIL_COLUMNS}
        from research_reports r
        join users u on u.id = r.created_by
        where r.id = $1 and r.org_id = $2
        """,
        report_id,
        org_id,
    )


async def list_for_org(
    pool: asyncpg.Pool,
    org_id: UUID,
    *,
    tag: str | None = None,
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[asyncpg.Record], int]:
    """Reports for one organization, newest first, plus the pre-pagination total.

    `tag` uses the GIN index on the array column and `search` the tsvector index
    on `query_text`, so neither filter degrades into a scan.
    """
    filters = ["r.org_id = $1"]
    params: list[Any] = [org_id]

    if tag and tag.strip():
        params.append(tag.strip().lower())
        filters.append(f"r.tags @> array[${len(params)}]::text[]")

    if search and search.strip():
        params.append(search.strip())
        filters.append(
            f"to_tsvector('english', r.query_text) @@ plainto_tsquery('english', ${len(params)})"
        )

    where = " and ".join(filters)

    total = await pool.fetchval(
        f"select count(*) from research_reports r where {where}",
        *params,
    )

    rows = await pool.fetch(
        f"""
        select {_SUMMARY_COLUMNS}
        from research_reports r
        join users u on u.id = r.created_by
        where {where}
        order by r.created_at desc, r.id desc
        limit ${len(params) + 1} offset ${len(params) + 2}
        """,
        *params,
        limit,
        offset,
    )
    return list(rows), int(total or 0)


async def update_tags(
    pool: asyncpg.Pool, org_id: UUID, report_id: UUID, tags: list[str]
) -> asyncpg.Record | None:
    """`updated_at` is maintained by a database trigger, not set here."""
    return await pool.fetchrow(
        f"""
        with updated as (
            update research_reports
            set tags = $3
            where id = $1 and org_id = $2
            returning *
        )
        select {_DETAIL_COLUMNS}
        from updated r
        join users u on u.id = r.created_by
        """,
        report_id,
        org_id,
        tags,
    )


async def delete(pool: asyncpg.Pool, org_id: UUID, report_id: UUID) -> bool:
    """True if a row was removed. False means it was absent or another org's."""
    result = await pool.execute(
        "delete from research_reports where id = $1 and org_id = $2",
        report_id,
        org_id,
    )
    return result.endswith(" 1")
