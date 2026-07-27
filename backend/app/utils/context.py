"""Per-request context.

The request id is held in a ContextVar so anything -- a log record, the
response envelope, an error handler -- can reach it without it being threaded
through every function signature.

Set once by the logging middleware, before the request reaches the router.
"""

from __future__ import annotations

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    return _request_id.get()


def set_request_id(value: str) -> Token[str | None]:
    return _request_id.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)
