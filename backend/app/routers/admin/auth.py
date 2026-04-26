import hashlib
import secrets

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
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
from app.services import rate_limit, recovery_codes, secret_box, totp
from app.services.auth import (
    create_access_token,
    issue_refresh,
    revoke_refresh,
    rotate_refresh,
    verify_password,
)
from app.services.event_log import write_event

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
    request: Request,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
):
    settings = get_settings()
    ip = request.client.host if request.client else "unknown"

    # Lockout check first.
    if await rate_limit.lockout_active(redis, f"login:{ip}"):
        retry = await rate_limit.lockout_retry_after(redis, f"login:{ip}")
        from app.errors import RateLimited
        raise RateLimited(retry_after=retry, detail="too many failures, locked out")

    # Per-minute throttle.
    await rate_limit.hit(redis, f"rl:login:{ip}", limit=5, window_sec=60)

    acct = (
        await s.execute(select(Account).where(Account.email == req.email))
    ).scalar_one_or_none()
    if acct is None or not verify_password(acct.password_hash, req.password):
        await rate_limit.mark_failure(
            redis,
            f"login:{ip}",
            threshold=settings.login_lockout_threshold,
            lock_window_sec=settings.login_lockout_window_sec,
        )
        await write_event(
            s,
            type="auth.login.fail",
            actor=req.email,
            meta={"ip": ip, "reason": "password" if acct else "unknown_email"},
        )
        await s.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")

    # Successful password — reset failure counter.
    await rate_limit.reset_failures(redis, f"login:{ip}")

    if acct.tfa_enabled:
        challenge = secrets.token_urlsafe(16)
        await redis.set(
            f"{CHALLENGE_PREFIX}{challenge}",
            str(acct.id),
            ex=settings.tfa_challenge_ttl,
        )
        return LoginChallengeResponse(challenge=challenge)

    result = await _issue_session_tokens(redis, response, acct)
    await write_event(s, type="auth.login.success", actor=acct.email, meta={"ip": ip})
    await s.commit()
    return result


@router.post("/auth/2fa", response_model=LoginResponse)
async def auth_2fa(
    req: TfaChallengeRequest,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> LoginResponse:
    await rate_limit.hit(
        redis, f"rl:2fa:{req.challenge}", limit=5, window_sec=300
    )

    sub = await redis.get(f"{CHALLENGE_PREFIX}{req.challenge}")
    if sub is None:
        raise HTTPException(401, "invalid or expired challenge")

    acct = (
        await s.execute(select(Account).where(Account.id == int(sub)))
    ).scalar_one_or_none()
    if acct is None or not acct.tfa_secret_encrypted:
        raise HTTPException(401, "account not configured")

    accepted = False
    code = req.code.strip()
    if len(code) == 6 and code.isdigit():
        secret = secret_box.decrypt(acct.tfa_secret_encrypted)
        accepted = totp.verify(secret, code)
    elif len(code) == 9 and code[4] == "-":
        accepted = await recovery_codes.verify_and_consume(
            s, account_id=acct.id, presented=code
        )
        if accepted:
            await s.commit()

    if not accepted:
        await write_event(s, type="auth.2fa.fail", actor=str(sub), meta={"challenge": req.challenge})
        await s.commit()
        raise HTTPException(401, "invalid code")

    await redis.delete(f"{CHALLENGE_PREFIX}{req.challenge}")
    result = await _issue_session_tokens(redis, response, acct)
    await write_event(
        s,
        type="auth.2fa.success",
        actor=acct.email,
        meta={"method": "totp" if (len(code) == 6) else "recovery"},
    )
    await s.commit()
    return result


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

    rotated = await rotate_refresh(redis, sub=sub, jti=_old_jti, presented_raw=raw)
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
    await write_event(s, type="auth.refresh", actor=str(sub), meta={"jti_old": _old_jti, "jti_new": new_jti})
    await s.commit()
    return RefreshResponse(access=access, expires_in=settings.access_token_ttl)


@router.post("/auth/logout", status_code=204)
async def logout(
    response: Response,
    redis: Redis = Depends(get_redis),
    raw_cookie: str | None = Cookie(default=None, alias=COOKIE_NAME),
    s: AsyncSession = Depends(get_session),
) -> Response:
    parsed = _parse_refresh_cookie(raw_cookie)
    if parsed is not None:
        sub, jti, _ = parsed
        await revoke_refresh(redis, sub=sub, jti=jti)
        await write_event(s, type="auth.logout", actor=sub, meta={"jti": jti})
        await s.commit()
    _clear_refresh_cookie(response)
    return Response(status_code=204)


@router.get("/session")
async def get_session_(admin: Account = Depends(current_admin)) -> dict:
    return {"id": admin.id, "email": admin.email, "tfa_enabled": admin.tfa_enabled}


from app.schemas.auth import MagicLinkRequest  # noqa: E402
from app.services import email as email_svc  # noqa: E402
from app.services import magic_link as magic_link_svc  # noqa: E402


@router.post("/auth/magic-link", status_code=202)
async def magic_link_request(
    req: MagicLinkRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    await rate_limit.hit(redis, f"rl:mlink:{req.email.lower()}", limit=3, window_sec=3600)
    acct = (
        await s.execute(select(Account).where(Account.email == req.email))
    ).scalar_one_or_none()
    if acct is None or not acct.magic_link_enabled:
        # Equalise timing: do dummy crypto + sleep close to issue+commit cost.
        import asyncio as _a
        hashlib.sha256(req.email.encode()).hexdigest()
        await _a.sleep(0.005)
        return {"ok": True}
    raw = await magic_link_svc.issue(s, account_id=acct.id)
    settings = get_settings()
    base = settings.public_api_base_url
    url = f"{base}/api/admin/auth/magic-link/verify?t={raw}"
    await email_svc.send_magic_link(email=acct.email, url=url)
    await write_event(
        s, type="auth.magic_link.requested", actor=req.email,
        meta={"email_hashed": hashlib.sha256(req.email.lower().encode()).hexdigest()[:12]},
    )
    await s.commit()
    return {"ok": True}


@router.get("/auth/magic-link/verify", response_model=LoginResponse)
async def magic_link_verify(
    t: str,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> LoginResponse:
    acct = await magic_link_svc.consume(s, raw=t)
    if acct is None:
        raise HTTPException(401, "invalid or expired magic link")
    result = await _issue_session_tokens(redis, response, acct)
    await write_event(s, type="auth.magic_link.consumed", actor=acct.email)
    await s.commit()
    return result
