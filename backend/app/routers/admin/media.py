from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, Media
from app.schemas.media import MediaItem, MediaPatch
from app.services import media as media_svc
from app.services.event_log import write_event
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


@router.patch(
    "/media/{media_id}",
    response_model=MediaItem,
    dependencies=[Depends(require_scope("write"))],
)
async def patch_media(
    media_id: int,
    req: MediaPatch,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> MediaItem:
    existing = await media_svc.get(s, media_id=media_id)
    if existing is None:
        raise HTTPException(404, "media not found")
    old_alt = existing.alt
    row = await media_svc.patch_alt(s, media_id=media_id, alt=req.alt)
    await write_event(
        s, type="media.alt_updated", actor=_admin.email,
        target=str(media_id), meta={"id": media_id, "old": old_alt, "new": req.alt},
    )
    await s.commit()
    return _to_item(row)
