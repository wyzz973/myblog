"""Email transport.

P5: send_email enqueues an ARQ task; the task body invokes _send_sync
in a thread. Dev fallback (smtp_host=None) still logs metadata only.

Inline test mode (settings.arq_inline=True) runs the task synchronously
in the same process so HTTP integration tests don't need a worker.
"""
from __future__ import annotations

import hashlib
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
        log.info(
            "email.dev_log",
            to=to, subject=subject,
            body_sha256=hashlib.sha256(body.encode()).hexdigest()[:12],
            body_len=len(body),
        )
        return
    from app.workers.queue import enqueue
    try:
        await enqueue("send_email_task", to=to, subject=subject, body=body)
    except Exception as e:  # noqa: BLE001
        log.warning("email.enqueue_failed", to=to, subject=subject, error=str(e))


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
