"""Failures from external providers.

Every integration raises one of these rather than leaking a provider-specific
exception, so the tool executor can degrade gracefully without knowing which
library threw. Each maps to a distinct HTTP status when it reaches a route.
"""

from __future__ import annotations


class UpstreamError(Exception):
    """Base class. Carries which provider failed, for logs and partial results."""

    status_code = 502

    def __init__(self, provider: str, message: str) -> None:
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class UpstreamTimeout(UpstreamError):
    """The provider did not answer within the configured budget."""

    status_code = 504


class UpstreamRateLimited(UpstreamError):
    """Quota exhausted. Retrying immediately will not help."""

    status_code = 429


class UpstreamUnavailable(UpstreamError):
    """Provider reachable but failing: 5xx, bad credentials, malformed body."""

    status_code = 502


class SymbolNotFound(UpstreamError):
    """The ticker does not exist. A caller error, not a provider failure."""

    status_code = 404
