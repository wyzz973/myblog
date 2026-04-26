from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.redis import get_redis
from app.schemas.auth import LoginRequest, LoginResponse, RefreshResponse
from app.services.auth import (
    create_access_token,
    issue_refresh,
    revoke_refresh,
    rotate_refresh,
    verify_password,
)

router = APIRouter()

COOKIE_NAME = "myblog_refresh"


def _set_refresh_cookie(resp: Response, raw: str, sub: str, jti: str) -> None:
    settings = get_settings()
    resp.set_cookie(
        key=COOKIE_NAME,
        value=f"{sub}.{jti}.{raw}",
        max_age=settings.refresh_token_ttl,
        path="/api/admin/auth",
        httponly=True,
        secure=settings.env == "prod",
        samesite="lax",
    )


def _clear_refresh_cookie(resp: Response) -> None:
    resp.delete_cookie(COOKIE_NAME, path="/api/admin/auth")


def _parse_refresh_cookie(raw_cookie: str | None) -> tuple[str, str, str] | None:
    if not raw_cookie:
        return None
    parts = raw_cookie.split(".", 2)
    if len(parts) != 3:
        return None
    sub, jti, raw = parts
    return sub, jti, raw


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> LoginResponse:
    acct = (
        await s.execute(select(Account).where(Account.email == req.email))
    ).scalar_one_or_none()
    if acct is None or not verify_password(acct.password_hash, req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    settings = get_settings()
    access = create_access_token(sub=str(acct.id), email=acct.email)
    raw, jti = await issue_refresh(redis, sub=str(acct.id))
    _set_refresh_cookie(response, raw, str(acct.id), jti)
    return LoginResponse(access=access, expires_in=settings.access_token_ttl)


@router.post("/auth/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response,
    redis: Redis = Depends(get_redis),
    raw_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    s: AsyncSession = Depends(get_session),
) -> RefreshResponse:
    parsed = _parse_refresh_cookie(raw_cookie)
    if parsed is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="missing refresh cookie")
    sub, _old_jti, raw = parsed

    rotated = await rotate_refresh(redis, sub=sub, presented_raw=raw)
    if rotated is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="invalid refresh token")
    new_raw, new_jti = rotated

    acct = (await s.execute(select(Account).where(Account.id == int(sub)))).scalar_one_or_none()
    if acct is None:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="account not found")

    settings = get_settings()
    access = create_access_token(sub=sub, email=acct.email)
    _set_refresh_cookie(response, new_raw, sub, new_jti)
    return RefreshResponse(access=access, expires_in=settings.access_token_ttl)


@router.post("/auth/logout", status_code=204)
async def logout(
    response: Response,
    redis: Redis = Depends(get_redis),
    raw_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> Response:
    parsed = _parse_refresh_cookie(raw_cookie)
    if parsed is not None:
        sub, jti, _ = parsed
        await revoke_refresh(redis, sub=sub, jti=jti)
    _clear_refresh_cookie(response)
    return Response(status_code=204)


@router.get("/session")
async def get_session_(admin: Account = Depends(current_admin)) -> dict:
    return {"id": admin.id, "email": admin.email, "tfa_enabled": admin.tfa_enabled}
