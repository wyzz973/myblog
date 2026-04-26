from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.auth import (
    TfaDisableRequest,
    TfaEnableRequest,
    TfaSetupResponse,
)
from app.services import secret_box, totp

router = APIRouter()


@router.post("/account/2fa/setup", response_model=TfaSetupResponse)
async def tfa_setup(
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> TfaSetupResponse:
    secret = totp.generate_secret()
    admin.tfa_secret_encrypted = secret_box.encrypt(secret)
    # do NOT enable yet; only after /enable verifies a code
    await s.commit()
    uri = totp.otpauth_uri(secret=secret, email=admin.email)
    return TfaSetupResponse(secret=secret, otpauth_uri=uri, qr_svg=totp.qr_svg(uri))


@router.post("/account/2fa/enable")
async def tfa_enable(
    req: TfaEnableRequest,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    if not admin.tfa_secret_encrypted:
        raise HTTPException(400, "no setup in progress")
    secret = secret_box.decrypt(admin.tfa_secret_encrypted)
    if not totp.verify(secret, req.code):
        raise HTTPException(400, "invalid code")
    admin.tfa_enabled = True
    await s.commit()
    # recovery codes are issued in Task 12 (placeholder for now)
    return {"tfa_enabled": True}


@router.delete("/account/2fa", status_code=204)
async def tfa_disable(
    req: TfaDisableRequest,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    if not admin.tfa_enabled or not admin.tfa_secret_encrypted:
        raise HTTPException(400, "2fa not enabled")
    secret = secret_box.decrypt(admin.tfa_secret_encrypted)
    if not totp.verify(secret, req.current_code):
        raise HTTPException(400, "invalid code")
    admin.tfa_enabled = False
    admin.tfa_secret_encrypted = None
    await s.commit()
    return Response(status_code=204)
