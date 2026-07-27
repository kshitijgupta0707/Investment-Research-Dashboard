"""The response envelope every endpoint returns.

Success and failure share one shape, so the frontend has a single parse path:
check `success`, then read `data` or `error`.

    { "success": true,  "data": {...}, "error": null,       "meta": {...} }
    { "success": false, "data": null,  "error": {...},      "meta": {...} }
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.utils.context import get_request_id

T = TypeVar("T")


class Meta(BaseModel):
    """Request metadata.

    `request_id` defaults to the current request's id, so every response is
    correlatable with its log line without callers passing it around.
    """

    request_id: str | None = Field(default_factory=get_request_id)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApiError(BaseModel):
    """A machine-readable code plus a human-readable message.

    Clients should branch on `code`; `message` is for display and may change.
    """

    code: str
    message: str
    details: list[Any] | None = None


class Envelope(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None
    meta: Meta = Field(default_factory=Meta)


def ok(data: T) -> Envelope[T]:
    return Envelope[T](success=True, data=data)


def fail(code: str, message: str, details: list[Any] | None = None) -> Envelope[None]:
    return Envelope[None](
        success=False,
        error=ApiError(code=code, message=message, details=details),
    )
