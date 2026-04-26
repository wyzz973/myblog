from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_session_admin
from app.models import Account
from app.schemas.auth import (
    MagicLinkToggleRequest,
    TfaDisableRequest,
    TfaEnableRequest,
    TfaRecoveryCodesResponse,
    TfaRegenerateRequest,
    TfaSetupResponse,
)
from app.services import recovery_codes, secret_box, totp
from app.services.event_log import write_event

router = APIRouter()


@router.post("/account/2fa/setup", response_model=TfaSetupResponse)
async def tfa_setup(
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> TfaSetupResponse:
    secret = totp.generate_secret()
    admin.tfa_secret_encrypted = secret_box.encrypt(secret)
    # do NOT enable yet; only after /enable verifies a code
    await s.commit()
    uri = totp.otpauth_uri(secret=secret, email=admin.email)
    return TfaSetupResponse(secret=secret, otpauth_uri=uri, qr_svg=totp.qr_svg(uri))


@router.post("/account/2fa/enable", response_model=TfaRecoveryCodesResponse)
async def tfa_enable(
    req: TfaEnableRequest,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> TfaRecoveryCodesResponse:
    if not admin.tfa_secret_encrypted:
        raise HTTPException(400, "no setup in progress")
    secret = secret_box.decrypt(admin.tfa_secret_encrypted)
    if not totp.verify(secret, req.code):
        raise HTTPException(400, "invalid code")
    admin.tfa_enabled = True
    raw = await recovery_codes.replace_for_account(s, account_id=admin.id)
    await write_event(s, type="account.2fa.enabled", actor=admin.email)
    await s.commit()
    return TfaRecoveryCodesResponse(recovery_codes=raw)


@router.delete("/account/2fa", status_code=204)
async def tfa_disable(
    req: TfaDisableRequest,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    if not admin.tfa_enabled or not admin.tfa_secret_encrypted:
        raise HTTPException(400, "2fa not enabled")
    secret = secret_box.decrypt(admin.tfa_secret_encrypted)
    if not totp.verify(secret, req.current_code):
        raise HTTPException(400, "invalid code")
    admin.tfa_enabled = False
    admin.tfa_secret_encrypted = None
    from sqlalchemy import delete as _del
    from app.models import TfaRecoveryCode
    await s.execute(_del(TfaRecoveryCode).where(TfaRecoveryCode.account_id == admin.id))
    await write_event(s, type="account.2fa.disabled", actor=admin.email)
    await s.commit()
    return Response(status_code=204)


@router.patch("/account/magic-link")
async def toggle_magic_link(
    req: MagicLinkToggleRequest,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    admin.magic_link_enabled = req.enabled
    await s.commit()
    return {"magic_link_enabled": admin.magic_link_enabled}


@router.post(
    "/account/2fa/recovery-codes/regenerate",
    response_model=TfaRecoveryCodesResponse,
)
async def tfa_regenerate_recovery_codes(
    req: TfaRegenerateRequest,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> TfaRecoveryCodesResponse:
    if not admin.tfa_enabled or not admin.tfa_secret_encrypted:
        raise HTTPException(400, "2fa not enabled")
    secret = secret_box.decrypt(admin.tfa_secret_encrypted)
    if not totp.verify(secret, req.current_code):
        raise HTTPException(400, "invalid code")
    raw = await recovery_codes.replace_for_account(s, account_id=admin.id)
    await write_event(s, type="account.recovery_codes.regenerated", actor=admin.email)
    await s.commit()
    return TfaRecoveryCodesResponse(recovery_codes=raw)
