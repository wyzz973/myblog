from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Media
from app.schemas.media import MediaItem
from app.services import media as media_svc
from app.services.media_storage import url_for

router = APIRouter()


def _to_item(row: Media) -> MediaItem:
    return MediaItem(
        id=row.id,
        filename=row.filename,
        url=url_for(row.storage_path),
        mime_type=row.mime_type,
        size=row.size,
        width=row.width,
        height=row.height,
        alt=row.alt,
        created_at=row.created_at,
    )


@router.get("/media", response_model=list[MediaItem])
async def list_media(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[MediaItem]:
    return [_to_item(r) for r in await media_svc.list_all(s)]


@router.get("/media/{media_id}", response_model=MediaItem)
async def get_media(
    media_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> MediaItem:
    row = await media_svc.get(s, media_id=media_id)
    if row is None:
        raise HTTPException(404, "media not found")
    return _to_item(row)
