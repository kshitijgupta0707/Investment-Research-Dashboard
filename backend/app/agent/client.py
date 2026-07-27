"""Shared Anthropic client and error translation.

Every Claude call in the agent goes through here, so the rest of the codebase
sees the same `UpstreamError` taxonomy as the market data and news providers
and can degrade the same way.
"""

from __future__ import annotations

from functools import lru_cache

import anthropic

from app.integrations.errors import (
    UpstreamError,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.utils.config import get_settings

PROVIDER = "anthropic"


@lru_cache
def get_client() -> anthropic.AsyncAnthropic:
    """One async client, reused across requests for connection pooling."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise UpstreamUnavailable(PROVIDER, "ANTHROPIC_API_KEY is not set")

    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )


def translate_error(exc: Exception) -> UpstreamError:
    """Map SDK exceptions onto our taxonomy.

    Ordered most specific first: RateLimitError and APITimeoutError are both
    subclasses of broader SDK errors, so a wider branch would swallow them.
    """
    if isinstance(exc, anthropic.APITimeoutError):
        return UpstreamTimeout(PROVIDER, "no response within the configured budget")
    if isinstance(exc, anthropic.RateLimitError):
        return UpstreamRateLimited(PROVIDER, "request quota exhausted")
    if isinstance(exc, anthropic.AuthenticationError):
        return UpstreamUnavailable(PROVIDER, "API key rejected")
    if isinstance(exc, anthropic.APIConnectionError):
        return UpstreamUnavailable(PROVIDER, "could not reach the API")
    if isinstance(exc, anthropic.BadRequestError):
        # A 400 here is our own misconfiguration -- a bad model id, an
        # exhausted credit balance, a malformed tool schema. The provider's
        # message is the only thing that says which, so keep it.
        return UpstreamUnavailable(PROVIDER, f"rejected the request: {exc.message}")
    if isinstance(exc, anthropic.APIStatusError):
        return UpstreamUnavailable(PROVIDER, f"HTTP {exc.status_code}")
    return UpstreamUnavailable(PROVIDER, str(exc) or exc.__class__.__name__)
