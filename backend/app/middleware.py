import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        # Stash on request.state so downstream handlers (incl. exception handlers)
        # can echo the same rid the response header carries.
        request.state.request_id = rid
        structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            # Unbind both keys so a stale rid never leaks into a background task
            # that captures the contextvars after the response returns.
            structlog.contextvars.unbind_contextvars("path", "request_id")
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
