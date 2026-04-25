from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventLog


async def write_event(
    session: AsyncSession,
    *,
    type: str,
    actor: str = "admin",
    target: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one event_log row inside the caller's session.

    Failures here MUST NOT block the main operation; we let exceptions surface
    only in dev (so tests catch missing columns); in prod, the caller wraps
    this in try/except. We keep it simple here.
    """
    session.add(EventLog(type=type, actor=actor, target=target, meta=meta or {}))
