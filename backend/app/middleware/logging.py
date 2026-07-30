"""Request id assignment and access logging.

Emits one structured line per request carrying the tenant context, so a log
search can answer "what did this org do" or "why was this request slow".
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.utils.context import REQUEST_ID_HEADER, reset_request_id, set_request_id

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Honour an inbound id so a request can be traced across services.
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = set_request_id(request_id)
        started = time.perf_counter()

        def elapsed_ms() -> float:
            return round((time.perf_counter() - started) * 1000, 2)

        def context(status_code: int) -> dict[str, object]:
            # Populated by the auth dependency once the caller is resolved.
            state = request.scope.get("state") or {}
            return {
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "latency_ms": elapsed_ms(),
                "user_id": state.get("user_id"),
                "org_id": state.get("org_id"),
            }

        try:
            response = await call_next(request)
        except Exception:
            # Logged here with timing and context; the 500 handler builds the
            # body. The id is deliberately left set -- that handler runs
            # *outside* this middleware, and resetting first would leave the
            # caller with a 500 carrying no id to quote back to us.
            logger.exception("request failed", extra={"context": context(500)})
            raise

        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info("request", extra={"context": context(response.status_code)})
        reset_request_id(token)
        return response
