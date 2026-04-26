"""Email sender — log-only in P3, replaced by ARQ+SMTP in P5."""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)


async def send_magic_link(*, email: str, url: str) -> None:
    log.info("magic_link.send", email=email, url=url)
