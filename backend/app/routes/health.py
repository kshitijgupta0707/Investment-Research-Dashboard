"""Liveness and dependency check."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import db
from app.schemas.envelope import Envelope, ok

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

_DB_TIMEOUT_SECONDS = 3.0


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["up", "down"]
    version: str


async def _database_reachable() -> bool:
    try:
        return await asyncio.wait_for(db.get_pool().fetchval("select 1"), _DB_TIMEOUT_SECONDS) == 1
    except (TimeoutError, Exception):  # noqa: B014 - any failure means "down"
        logger.warning("health check: database unreachable", exc_info=True)
        return False


@router.get("/health", response_model=Envelope[Health])
async def health() -> Envelope[Health]:
    """Always 200; read `data.status` to distinguish healthy from degraded.

    A monitor that treats any non-200 as down would otherwise get no detail
    about *which* dependency failed.
    """
    reachable = await _database_reachable()
    return ok(
        Health(
            status="ok" if reachable else "degraded",
            database="up" if reachable else "down",
            version="0.1.0",
        )
    )
