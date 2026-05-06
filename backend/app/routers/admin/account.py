from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_session_admin
from app.models import Account
from app.schemas.auth import (
    EmailChangeConfirmRequest,
    EmailChangeConfirmResponse,
    EmailChangeRequest,
    EmailChangeRequestMagic,
    MagicLinkToggleRequest,
    PasswordChangeRequest,
    TfaDisableRequest,
    TfaEnableRequest,
    TfaRecoveryCodesResponse,
    TfaRegenerateRequest,
    TfaSetupResponse,
)
from app.services import (
    email as email_svc,
    pending_email_change as pending_email_svc,
    recovery_codes,
    secret_box,
    totp,
)
from app.services.auth import hash_password, verify_password
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


@router.post("/account/password", status_code=204)
async def change_password(
    req: PasswordChangeRequest,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    if not verify_password(admin.password_hash, req.current_password):
        raise HTTPException(400, "current password is incorrect")
    if req.new_password == req.current_password:
        raise HTTPException(400, "new password must differ from current")
    admin.password_hash = hash_password(req.new_password)
    await write_event(s, type="account.password.changed", actor=admin.email)
    await s.commit()
    return Response(status_code=204)


# Task 28a: rotate the admin email. Session-only (api tokens explicitly
# rejected via current_session_admin) and password-gated. Single-account
# site so a unique-collision check is unnecessary today, but we still
# normalize to lowercase to avoid case-only "changes" flying through.
@router.post("/account/email")
async def change_email(
    req: EmailChangeRequest,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    if not verify_password(admin.password_hash, req.current_password):
        raise HTTPException(400, "current password is incorrect")
    new_email = req.new_email.strip().lower()
    if new_email == admin.email.lower():
        raise HTTPException(400, "new email must differ from current")
    old_email = admin.email
    admin.email = new_email
    await write_event(
        s, type="account.email.changed", actor=old_email,
        meta={"old": old_email, "new": new_email},
    )
    await s.commit()
    return {"email": admin.email}


# Task 28c: two-step email rotation. Step 1 — request the change. Verifies
# the password and sends a magic link to the *new* address; the existing
# email keeps working until step 2 confirms via the token.
@router.post("/account/email/request")
async def request_email_change(
    req: EmailChangeRequestMagic,
    request: Request,
    admin: Account = Depends(current_session_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    if not verify_password(admin.password_hash, req.current_password):
        raise HTTPException(400, "current password is incorrect")
    new_email = req.new_email.strip().lower()
    if new_email == admin.email.lower():
        raise HTTPException(400, "new email must differ from current")

    raw = await pending_email_svc.issue(
        s,
        account_id=admin.id,
        new_email=new_email,
        requested_ip=(request.client.host if request.client else None),
        user_agent=request.headers.get("user-agent"),
    )
    settings = get_settings()
    url = f"{settings.public_site_base_url}/admin/account/email-confirm?token={raw}"
    await email_svc.send_email_change_confirm(email=new_email, url=url)
    await write_event(
        s, type="account.email.change_requested",
        actor=admin.email, meta={"new_email": new_email},
    )
    await s.commit()
    return {"sent": True, "to": new_email}


# Task 28c: step 2 — confirm. Consumes the one-shot token; rotation
# happens here. Public (no session) so the link works even if the user is
# logged out in the new browser/device they're confirming from.
@router.post("/account/email/confirm", response_model=EmailChangeConfirmResponse)
async def confirm_email_change(
    req: EmailChangeConfirmRequest,
    s: AsyncSession = Depends(get_session),
) -> EmailChangeConfirmResponse:
    result = await pending_email_svc.consume(s, raw=req.token)
    if result is None:
        raise HTTPException(400, "invalid or expired token")
    account_id, new_email = result
    acct = (
        await s.execute(select(Account).where(Account.id == account_id))
    ).scalar_one_or_none()
    if acct is None:
        raise HTTPException(404, "account not found")
    if new_email == acct.email.lower():
        # Race: another request already rotated to this address. Idempotent.
        return EmailChangeConfirmResponse(email=acct.email)
    old_email = acct.email
    acct.email = new_email
    await write_event(
        s, type="account.email.changed", actor=old_email,
        meta={"old": old_email, "new": new_email, "via": "magic_link"},
    )
    await s.commit()
    return EmailChangeConfirmResponse(email=acct.email)


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
