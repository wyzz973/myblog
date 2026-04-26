"""ARQ task implementations."""
from __future__ import annotations

import asyncio
from typing import Any

import structlog

log = structlog.get_logger(__name__)


async def send_email_task(ctx: dict, *, to: str, subject: str, body: str) -> dict:
    """Run smtplib send in a thread; ARQ handles retry-with-backoff.

    On exception, ARQ records the failure; we also log a WARNING so the
    failure is visible in structlog output.
    """
    from app.services.email import _send_sync
    try:
        await asyncio.to_thread(_send_sync, to=to, subject=subject, body=body)
        log.info("email.sent", to=to, subject=subject)
        return {"ok": True}
    except Exception as e:  # noqa: BLE001
        log.warning("email.send_failed", to=to, subject=subject, error=str(e))
        # raise so ARQ retries (3 attempts default with backoff)
        raise


# job-level retry config (ARQ reads these from the function)
send_email_task.max_tries = 3
