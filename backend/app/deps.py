from typing import Literal

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import AuthError
from app.models import Account
from app.services import api_tokens as api_tokens_svc
from app.services.auth import decode_access_token


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    return authorization.split(None, 1)[1].strip()


async def _admin_from_jwt(token: str, s: AsyncSession) -> Account:
    payload = decode_access_token(token)
    acct = (
        await s.execute(select(Account).where(Account.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if acct is None or acct.email != payload.get("email"):
        raise AuthError("account not found")
    return acct


async def current_admin(
    request: Request,
    authorization: str | None = Header(None),
    s: AsyncSession = Depends(get_session),
) -> Account:
    """Accepts a JWT access token (session) OR an api-token (scope-checked elsewhere).

    On api-token success, the request.state is annotated with `api_token_scope`
    so `require_scope(...)` can enforce write protection.
    """
    raw = _bearer(authorization)
    if raw.startswith("tk_"):
        row = await api_tokens_svc.verify(s, raw)
        if row is None:
            raise AuthError("invalid api token")
        request.state.api_token_scope = row.scope
        request.state.api_token_id = row.id   # for touch downstream
        # Reuse the singleton admin row for downstream endpoints that
        # display "actor".
        acct = (
            await s.execute(select(Account).where(Account.id == 1))
        ).scalar_one_or_none()
        if acct is None:
            raise AuthError("admin account missing")
        return acct
    request.state.api_token_scope = None  # session
    return await _admin_from_jwt(raw, s)


async def current_session_admin(
    request: Request,
    admin: Account = Depends(current_admin),
) -> Account:
    """Reject api-tokens; only session JWT may manage 2FA/recovery codes."""
    if getattr(request.state, "api_token_scope", None) is not None:
        raise AuthError("session required")
    return admin


def require_scope(scope: Literal["read", "write"]):
    async def _dep(
        request: Request,
        _admin: Account = Depends(current_admin),
        s: AsyncSession = Depends(get_session),
    ) -> None:
        token_scope = getattr(request.state, "api_token_scope", None)
        if token_scope is None:
            return  # session JWT — full access
        if scope == "write" and token_scope != "write":
            raise HTTPException(status_code=403, detail="api token has read scope only")
        # Bump last_used_at + usage_count on the scope-passing path. Note:
        # endpoints without require_scope (pure-read paths like /dashboard)
        # do NOT tick the counter; only scope-checked uses do.
        token_id = getattr(request.state, "api_token_id", None)
        if token_id is not None:
            await api_tokens_svc.touch_last_used(s, token_id=token_id)

    return _dep
