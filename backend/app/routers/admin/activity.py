from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.activity import ActivityItem
from app.services import activity

router = APIRouter()


@router.get("/activity", response_model=list[ActivityItem])
async def list_activity(
    type: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ActivityItem]:
    rows = await activity.list_events(s, types=type, limit=limit, offset=offset)
    return [
        ActivityItem(
            id=r.id, type=r.type, actor=r.actor, target=r.target,
            meta=r.meta or {}, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/dashboard/activity", response_model=list[ActivityItem])
async def dashboard_activity(
    limit: int = Query(default=20, ge=1, le=100),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ActivityItem]:
    rows = await activity.list_events(s, limit=limit, offset=0)
    return [
        ActivityItem(
            id=r.id, type=r.type, actor=r.actor, target=r.target,
            meta=r.meta or {}, created_at=r.created_at,
        )
        for r in rows
    ]
