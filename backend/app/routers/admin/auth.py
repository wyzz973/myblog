from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import create_access_token, verify_password

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest, s: AsyncSession = Depends(get_session)) -> LoginResponse:
    acct = (
        await s.execute(select(Account).where(Account.email == req.email))
    ).scalar_one_or_none()
    if acct is None or not verify_password(acct.password_hash, req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    settings = get_settings()
    token = create_access_token(sub=str(acct.id), email=acct.email)
    return LoginResponse(access=token, expires_in=settings.access_token_ttl)


@router.get("/session")
async def get_session_(admin: Account = Depends(current_admin)) -> dict:
    return {"id": admin.id, "email": admin.email, "tfa_enabled": admin.tfa_enabled}
