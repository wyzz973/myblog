"""Email transport.

Two modes selected at call time via settings.smtp_host:

  - smtp_host = None  → dev fallback: structlog.info() the event and
    return. Used when the operator hasn't wired SMTP yet.
  - smtp_host = "..." → run smtplib.SMTP(host, port) in asyncio.to_thread,
    optional STARTTLS + login, send_message.

Failures inside SMTP mode are caught and logged at WARNING. The caller's
business path (comment submission, magic-link issuance) MUST NOT fail
because email transport failed.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def _send_sync(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(msg)


async def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if settings.smtp_host is None:
        log.info("email.dev_log", to=to, subject=subject, body_preview=body[:120])
        return
    try:
        await asyncio.to_thread(_send_sync, to=to, subject=subject, body=body)
        log.info("email.sent", to=to, subject=subject)
    except Exception as e:  # noqa: BLE001
        log.warning("email.send_failed", to=to, subject=subject, error=str(e))


async def send_magic_link(*, email: str, url: str) -> None:
    subject = "Your wangyang.dev magic-link"
    body = (
        f"Click to sign in: {url}\n\n"
        "Valid for 15 minutes. If you didn't request this, ignore this email."
    )
    await send_email(to=email, subject=subject, body=body)


async def send_comment_notification(
    *, to: str, comment_id: int, post_id: str, who: str, snippet: str
) -> None:
    subject = f"[wangyang.dev] new comment on {post_id}"
    body = (
        f"From: {who}\n\n"
        f"{snippet[:280]}\n\n"
        f"Moderate: /admin#comments/{comment_id}"
    )
    await send_email(to=to, subject=subject, body=body)
