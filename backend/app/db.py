"""Postgres connection pool.

Opened once at application startup and shared by every request. The pool
connects with a privileged role, so Row-Level Security does not constrain it --
tenant scoping is the caller's responsibility on every query.
"""

from __future__ import annotations

import json

import asyncpg

from app.utils.config import get_settings

_pool: asyncpg.Pool | None = None


async def _register_codecs(connection: asyncpg.Connection) -> None:
    """Hand jsonb columns back as Python objects rather than strings.

    Without this, `audit_logs.metadata` and `research_reports.structured_result`
    round-trip as raw JSON text and every caller has to remember to dumps/loads
    them.
    """
    await connection.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def connect() -> asyncpg.Pool:
    """Create the pool. Safe to call twice; the second call is a no-op."""
    global _pool
    if _pool is not None:
        return _pool

    database_url = get_settings().database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

    _pool = await asyncpg.create_pool(
        database_url,
        min_size=1,
        max_size=10,
        command_timeout=30,
        init=_register_codecs,
    )
    return _pool


async def disconnect() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised.")
    return _pool
