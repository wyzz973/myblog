from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.now import NowEntryItem, NowPublicResponse
from app.services import now as now_svc

router = APIRouter()


def _item(row) -> NowEntryItem:
    return NowEntryItem(
        id=row.id, body_md=row.body_md, listening=row.listening,
        reading=row.reading, is_current=row.is_current, created_at=row.created_at,
    )


@router.get("/now", response_model=NowPublicResponse)
async def public_now(s: AsyncSession = Depends(get_session)) -> NowPublicResponse:
    current = await now_svc.get_current(s)
    history = await now_svc.history(s, limit=10)
    return NowPublicResponse(
        current=_item(current) if current else None,
        history=[_item(r) for r in history],
    )
