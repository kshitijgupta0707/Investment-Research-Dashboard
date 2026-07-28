"""Shared Gemini client and error translation.

Every model call in the agent goes through here, so the rest of the codebase
sees the same `UpstreamError` taxonomy as the market data and news providers
and can degrade the same way.

The SDK collapses every HTTP failure into `ClientError` (4xx) and `ServerError`
(5xx) rather than exposing a class per status, so the status code is what the
mapping below branches on.
"""

from __future__ import annotations

import httpx
from functools import lru_cache

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.integrations.errors import (
    UpstreamError,
    UpstreamRateLimited,
    UpstreamTimeout,
    UpstreamUnavailable,
)
from app.utils.config import get_settings

PROVIDER = "gemini"


@lru_cache
def get_client() -> genai.Client:
    """One client, reused across requests for connection pooling.

    Calls are made through `client.aio`, which is the async surface; the client
    object itself is shared.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        raise UpstreamUnavailable(PROVIDER, "GEMINI_API_KEY is not set")

    return genai.Client(
        api_key=settings.gemini_api_key,
        # HttpOptions.timeout is milliseconds, unlike every other timeout in
        # this codebase; converted here so callers keep working in seconds.
        http_options=types.HttpOptions(timeout=int(settings.llm_timeout_seconds * 1000)),
    )


def translate_error(exc: Exception) -> UpstreamError:
    """Map SDK exceptions onto our taxonomy.

    Ordered most specific first. `ClientError` and `ServerError` both subclass
    `APIError`, so the broad branch has to come last or it swallows them.
    """
    if isinstance(exc, (httpx.TimeoutException, TimeoutError)):
        return UpstreamTimeout(PROVIDER, "no response within the configured budget")

    if isinstance(exc, genai_errors.ClientError):
        if exc.code == 429:
            return UpstreamRateLimited(PROVIDER, "request quota exhausted")
        if exc.code in (401, 403):
            return UpstreamUnavailable(PROVIDER, "API key rejected")
        # A 400 here is our own misconfiguration -- a bad model id, an exhausted
        # quota, a malformed tool schema. The provider's message is the only
        # thing that says which, so keep it.
        return UpstreamUnavailable(PROVIDER, f"rejected the request: {exc.message}")

    if isinstance(exc, genai_errors.ServerError):
        return UpstreamUnavailable(PROVIDER, f"HTTP {exc.code}")

    if isinstance(exc, genai_errors.APIError):
        return UpstreamUnavailable(PROVIDER, f"HTTP {getattr(exc, 'code', '?')}")

    if isinstance(exc, httpx.HTTPError):
        return UpstreamUnavailable(PROVIDER, "could not reach the API")

    return UpstreamUnavailable(PROVIDER, str(exc) or exc.__class__.__name__)


# --- reading responses ------------------------------------------------------
#
# A blocked or empty response has no candidates at all, and a candidate can
# carry no content. Both are normal outcomes rather than errors, so these walk
# the structure defensively instead of indexing into it.


def response_parts(response: types.GenerateContentResponse) -> list[types.Part]:
    """Every part of the first candidate, or an empty list."""
    for candidate in response.candidates or []:
        content = getattr(candidate, "content", None)
        return list(getattr(content, "parts", None) or [])
    return []


def finish_reason(response: types.GenerateContentResponse) -> str | None:
    """The first candidate's finish reason, as a plain string for logging."""
    for candidate in response.candidates or []:
        reason = getattr(candidate, "finish_reason", None)
        if reason is None:
            return None
        return getattr(reason, "value", None) or str(reason)
    return None
