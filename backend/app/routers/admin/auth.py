import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.redis import get_redis
from app.schemas.auth import (
    LoginChallengeResponse,
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    TfaChallengeRequest,
)
from app.services import secret_box, totp
from app.services.auth import (
    create_access_token,
    issue_refresh,
    revoke_refresh,
    rotate_refresh,
    verify_password,
)

router = APIRouter()

COOKIE_NAME = "myblog_refresh"
CHALLENGE_PREFIX = "2fa:"


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
    return parts[0], parts[1], parts[2]


async def _issue_session_tokens(redis: Redis, response: Response, acct: Account) -> LoginResponse:
    settings = get_settings()
    access = create_access_token(sub=str(acct.id), email=acct.email)
    raw, jti = await issue_refresh(redis, sub=str(acct.id))
    _set_refresh_cookie(response, raw, str(acct.id), jti)
    return LoginResponse(access=access, expires_in=settings.access_token_ttl)


@router.post("/auth/login")
async def login(
    req: LoginRequest,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    settings = get_settings()
    acct = (
        await s.execute(select(Account).where(Account.email == req.email))
    ).scalar_one_or_none()
    if acct is None or not verify_password(acct.password_hash, req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    if acct.tfa_enabled:
        challenge = secrets.token_urlsafe(16)
        await redis.set(
            f"{CHALLENGE_PREFIX}{challenge}",
            str(acct.id),
            ex=settings.tfa_challenge_ttl,
        )
        return LoginChallengeResponse(challenge=challenge)

    return await _issue_session_tokens(redis, response, acct)


@router.post("/auth/2fa", response_model=LoginResponse)
async def auth_2fa(
    req: TfaChallengeRequest,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> LoginResponse:
    sub = await redis.get(f"{CHALLENGE_PREFIX}{req.challenge}")
    if sub is None:
        raise HTTPException(401, "invalid or expired challenge")

    acct = (
        await s.execute(select(Account).where(Account.id == int(sub)))
    ).scalar_one_or_none()
    if acct is None or not acct.tfa_secret_encrypted:
        raise HTTPException(401, "account not configured")

    secret = secret_box.decrypt(acct.tfa_secret_encrypted)
    if not totp.verify(secret, req.code):
        # Recovery-code path is added in Task 12.
        raise HTTPException(401, "invalid code")

    await redis.delete(f"{CHALLENGE_PREFIX}{req.challenge}")
    return await _issue_session_tokens(redis, response, acct)


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
        raise HTTPException(401, "missing refresh cookie")
    sub, _old_jti, raw = parsed

    rotated = await rotate_refresh(redis, sub=sub, presented_raw=raw)
    if rotated is None:
        _clear_refresh_cookie(response)
        raise HTTPException(401, "invalid refresh token")
    new_raw, new_jti = rotated

    acct = (await s.execute(select(Account).where(Account.id == int(sub)))).scalar_one_or_none()
    if acct is None:
        _clear_refresh_cookie(response)
        raise HTTPException(401, "account not found")

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
