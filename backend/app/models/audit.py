"""The audit trail.

Writes are best-effort. Losing one audit line is bad; refusing a user's request
because the audit insert had a hiccup is worse -- and the action has usually
already happened by the time the entry is written, so raising would report a
failure that did not occur.

`audit_logs` has no RLS insert policy, so only the application's privileged
connection writes here. Users can read their organization's history but can
never forge an entry.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import asyncpg

logger = logging.getLogger(__name__)


async def record(
    pool: asyncpg.Pool,
    *,
    org_id: UUID,
    user_id: UUID | None,
    action: str,
    entity_type: str | None = None,
    entity_id: UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Append one entry. Never raises."""
    try:
        await pool.execute(
            """
            insert into audit_logs (org_id, user_id, action, entity_type, entity_id, metadata)
            values ($1, $2, $3, $4, $5, $6)
            """,
            org_id,
            user_id,
            action,
            entity_type,
            entity_id,
            metadata or {},
        )
    except Exception:
        logger.exception(
            "failed to write audit log",
            extra={
                "context": {
                    "action": action,
                    "entity_id": str(entity_id) if entity_id else None,
                }
            },
        )
