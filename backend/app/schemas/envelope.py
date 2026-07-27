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

T = TypeVar("T")


class Meta(BaseModel):
    """Request metadata. `request_id` is populated by the logging middleware."""

    request_id: str | None = None
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


def ok(data: T, request_id: str | None = None) -> Envelope[T]:
    return Envelope[T](success=True, data=data, meta=Meta(request_id=request_id))


def fail(
    code: str,
    message: str,
    details: list[Any] | None = None,
    request_id: str | None = None,
) -> Envelope[None]:
    return Envelope[None](
        success=False,
        error=ApiError(code=code, message=message, details=details),
        meta=Meta(request_id=request_id),
    )
