from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = structlog.get_logger(__name__)


class AuthError(Exception):
    def __init__(self, detail: str = "auth required") -> None:
        self.detail = detail


class NotFoundError(Exception):
    def __init__(self, detail: str = "not found") -> None:
        self.detail = detail


class RateLimited(Exception):
    def __init__(self, retry_after: int = 60, detail: str = "rate limited") -> None:
        self.retry_after = retry_after
        self.detail = detail


def _err(status_code: int, detail: Any, **headers: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers or None)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, e: HTTPException) -> JSONResponse:
        return _err(e.status_code, e.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError) -> JSONResponse:
        return _err(status.HTTP_422_UNPROCESSABLE_ENTITY, e.errors())

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, e: IntegrityError) -> JSONResponse:
        logger.warning("integrity_error", error=str(e.orig))
        return _err(status.HTTP_409_CONFLICT, "conflict")

    @app.exception_handler(AuthError)
    async def _auth(_: Request, e: AuthError) -> JSONResponse:
        return _err(status.HTTP_401_UNAUTHORIZED, e.detail)

    @app.exception_handler(NotFoundError)
    async def _nf(_: Request, e: NotFoundError) -> JSONResponse:
        return _err(status.HTTP_404_NOT_FOUND, e.detail)

    @app.exception_handler(RateLimited)
    async def _rl(_: Request, e: RateLimited) -> JSONResponse:
        return _err(
            status.HTTP_429_TOO_MANY_REQUESTS, e.detail, **{"Retry-After": str(e.retry_after)}
        )

    @app.exception_handler(Exception)
    async def _unhandled(req: Request, e: Exception) -> JSONResponse:
        rid = req.headers.get("X-Request-ID", "?")
        logger.exception("unhandled_exception", error=str(e), request_id=rid)
        return _err(status.HTTP_500_INTERNAL_SERVER_ERROR, f"internal error · {rid}")
