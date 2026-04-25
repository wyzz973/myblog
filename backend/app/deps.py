from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import AuthError
from app.models import Account
from app.services.auth import decode_access_token


async def current_admin(
    authorization: str | None = Header(None),
    s: AsyncSession = Depends(get_session),
) -> Account:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    payload = decode_access_token(authorization.split(None, 1)[1].strip())
    acct = (
        await s.execute(select(Account).where(Account.id == int(payload["sub"])))
    ).scalar_one_or_none()
    if acct is None or acct.email != payload.get("email"):
        raise AuthError("account not found")
    return acct
