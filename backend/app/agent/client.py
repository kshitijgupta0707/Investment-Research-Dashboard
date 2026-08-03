"""Shared Gemini client and error translation.

Every model call in the agent goes through here, so the rest of the codebase
sees the same `UpstreamError` taxonomy as the market data and news providers
and can degrade the same way.

The SDK collapses every HTTP failure into `ClientError` (4xx) and `ServerError`
(5xx) rather than exposing a class per status, so the status code is what the
mapping below branches on.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import httpx

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

logger = logging.getLogger(__name__)

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
    # Idempotent: `generate` below translates before deciding whether to fall
    # back, and its callers translate again. Without this an already-classified
    # rate limit would fall through to the catch-all and be reported as a
    # generic outage, losing the 429 the API actually sent.
    if isinstance(exc, UpstreamError):
        return exc

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


# --- making calls -----------------------------------------------------------


async def generate(
    *, contents: Any, config: types.GenerateContentConfig, purpose: str
) -> types.GenerateContentResponse:
    """One model call, retried on a second model when the first is rate limited.

    Free-tier quota is granted per model -- the 429 names
    `GenerateRequestsPerMinutePerProjectPerModel` -- so the fallback still has
    its own allowance when the primary has none. Same shape as
    `FallbackMarketDataClient`: try the preferred provider, drop to the
    documented alternative on a failure a second attempt could survive.

    **Only a rate limit triggers it.** A timeout, a rejected key or a malformed
    request would fail identically on the second model, so retrying would double
    the latency to reach the same error.

    `purpose` names the calling stage -- "planning", "sentiment", "synthesis" --
    so a log search can tell which one degraded.
    """
    settings = get_settings()
    client = get_client()

    models = [settings.gemini_model]
    if settings.gemini_fallback_model:
        models.append(settings.gemini_fallback_model)

    for index, model in enumerate(models):
        last_attempt = index == len(models) - 1

        try:
            response = await client.aio.models.generate_content(
                model=model, contents=contents, config=config
            )
        except Exception as exc:
            error = translate_error(exc)
            logger.warning(
                "gemini call failed",
                extra={
                    "context": {
                        "purpose": purpose,
                        "model": model,
                        "is_fallback": index > 0,
                        "error": str(error),
                    }
                },
            )
            if last_attempt or not isinstance(error, UpstreamRateLimited):
                raise error from exc
            continue

        if index > 0:
            logger.info(
                "served by the fallback model",
                extra={
                    "context": {
                        "purpose": purpose,
                        "model": response.model_version or model,
                        "primary_model": settings.gemini_model,
                    }
                },
            )
        return response

    # Unreachable: the loop either returns or raises on its last attempt.
    raise UpstreamUnavailable(PROVIDER, "no model was attempted")


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
