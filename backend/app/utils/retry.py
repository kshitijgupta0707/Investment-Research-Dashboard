"""Retry helper for external calls.

Deliberately narrow: retries transient failures only. A rate limit is not
transient on a free tier -- retrying burns the remaining quota and delays the
response for nothing -- and a missing symbol will never become present.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.integrations.errors import UpstreamTimeout, UpstreamUnavailable

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE = (UpstreamTimeout, UpstreamUnavailable)


async def with_retry(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int = 2,
    base_delay: float = 0.4,
    label: str = "upstream call",
) -> T:
    """Run `operation`, retrying transient failures with exponential backoff."""
    last: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except RETRYABLE as exc:
            last = exc
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "%s failed, retrying in %.1fs (attempt %d/%d): %s",
                label,
                delay,
                attempt,
                attempts,
                exc,
            )
            await asyncio.sleep(delay)

    assert last is not None
    raise last
