"""Global exception handling.

Every error leaves the application through here, so a client never sees a raw
stack trace or an inconsistent body. Handlers are registered in `main.py`.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.envelope import fail

logger = logging.getLogger(__name__)

# Status codes carry the contract; these codes let a client branch without
# hard-coding numbers.
_CODES: dict[int, str] = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
    502: "UPSTREAM_ERROR",
    503: "SERVICE_UNAVAILABLE",
    504: "UPSTREAM_TIMEOUT",
}


def code_for(status_code: int) -> str:
    if status_code in _CODES:
        return _CODES[status_code]
    return "CLIENT_ERROR" if 400 <= status_code < 500 else "INTERNAL_ERROR"


def _envelope(status_code: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    body = fail(code=code, message=message, details=details)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body))


async def handle_http_exception(_: Request, exc: Exception) -> JSONResponse:
    """Anything raised as HTTPException, including 401/403 from the guards."""
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    response = _envelope(exc.status_code, code_for(exc.status_code), detail)

    # Preserve auth challenge headers such as WWW-Authenticate.
    for key, value in (getattr(exc, "headers", None) or {}).items():
        response.headers[key] = value
    return response


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    """Pydantic rejected the request body, query or path.

    FastAPI defaults to 422; the API contract specifies 400 for validation.
    """
    assert isinstance(exc, RequestValidationError)
    return _envelope(400, "VALIDATION_ERROR", "Request validation failed.", jsonable_encoder(exc.errors()))


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Last resort. Logged in full, reported vaguely."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return _envelope(500, "INTERNAL_ERROR", "An unexpected error occurred.")


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unexpected_error)
