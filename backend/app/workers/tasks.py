"""ARQ task implementations. Each function takes ctx (worker context) as first arg."""
from __future__ import annotations

from typing import Any


async def send_email_task(ctx: dict, *, to: str, subject: str, body: str) -> dict:
    """Synchronous SMTP send wrapped in asyncio.to_thread (registered in Task 6)."""
    raise NotImplementedError("registered in Task 6")
