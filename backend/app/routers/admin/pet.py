import base64
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, PetMessage, SiteMeta
from app.schemas.pet import PetConfig, PetModeTemplates, PetPersonas

router = APIRouter()

ResetSection = Literal["personas", "templates", "both"]


def _encode_cursor(last_msg_at: datetime, visitor_hash: str) -> str:
    raw = f"{last_msg_at.isoformat()}|{visitor_hash}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, vh = raw.rsplit("|", 1)
        return datetime.fromisoformat(ts_str), vh
    except Exception:
        return None


@router.get("/pet", response_model=PetConfig)
async def get_pet(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.put("/pet", response_model=PetConfig, dependencies=[Depends(require_scope("write"))])
async def put_pet(
    req: PetConfig,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=req.model_dump())
    )
    await s.commit()
    return req


@router.get("/pet/defaults")
async def get_pet_defaults(
    _admin: Account = Depends(current_admin),
) -> dict:
    """Return schema defaults for personas + mode_templates so the frontend
    'Reset to defaults' button doesn't have to keep its own copy."""
    defaults = PetConfig()
    return {
        "personas": defaults.personas.model_dump(),
        "mode_templates": defaults.mode_templates.model_dump(),
    }


@router.post(
    "/pet/reset",
    response_model=PetConfig,
    dependencies=[Depends(require_scope("write"))],
)
async def reset_pet_section(
    section: ResetSection = Query(...),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PetConfig:
    """Reset personas / templates / both back to schema defaults.
    Other PetConfig fields are preserved."""
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    cur = PetConfig(**{**PetConfig().model_dump(), **(site.pet_config or {})})
    payload = cur.model_dump()
    if section in ("personas", "both"):
        payload["personas"] = PetPersonas().model_dump()
    if section in ("templates", "both"):
        payload["mode_templates"] = PetModeTemplates().model_dump()
    new = PetConfig(**payload)
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=new.model_dump())
    )
    await s.commit()
    return new


@router.get("/pet/conversations")
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    species: str | None = Query(default=None, max_length=32),
    since: datetime | None = Query(default=None),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List conversations grouped by visitor_hash, ordered by last_msg_at desc."""
    # Step 1: aggregate query — visitor_hash, max(created_at), count(id)
    stmt = (
        select(
            PetMessage.visitor_hash,
            func.max(PetMessage.created_at).label("last_msg_at"),
            func.count(PetMessage.id).label("message_count"),
        )
        .group_by(PetMessage.visitor_hash)
    )
    if species:
        stmt = stmt.where(PetMessage.species == species)
    if since:
        stmt = stmt.where(PetMessage.created_at >= since)

    # Cursor logic: filter rows older than (ts, vh) using HAVING (compound cursor).
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            ts, vh = decoded
            stmt = stmt.having(
                (func.max(PetMessage.created_at) < ts)
                | (
                    (func.max(PetMessage.created_at) == ts)
                    & (PetMessage.visitor_hash > vh)
                )
            )

    stmt = stmt.order_by(desc("last_msg_at"), PetMessage.visitor_hash).limit(limit + 1)

    rows = (await s.execute(stmt)).all()
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        # Per-visitor follow-up: latest species + latest reply preview
        latest = (await s.execute(
            select(PetMessage.species, PetMessage.reply, PetMessage.created_at)
            .where(PetMessage.visitor_hash == row.visitor_hash)
            .order_by(desc(PetMessage.created_at))
            .limit(1)
        )).first()
        items.append({
            "visitor_hash": row.visitor_hash,
            "species": latest.species if latest else "unknown",
            "last_msg_at": row.last_msg_at.isoformat(),
            "message_count": int(row.message_count),
            "last_reply_preview": (latest.reply or "")[:80] if latest else "",
        })
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        next_cursor = _encode_cursor(
            datetime.fromisoformat(last["last_msg_at"]),
            last["visitor_hash"],
        )
    return {"items": items, "next_cursor": next_cursor}
