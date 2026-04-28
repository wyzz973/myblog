from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal, get_session
from app.deps import current_admin, require_scope
from app.models import Account, Media
from app.schemas.media import (
    MediaItem,
    MediaPatch,
    MediaUploadFailure,
    MediaUploadResponse,
)
from app.services import media as media_svc
from app.services import media_storage
from app.services.event_log import write_event
from app.services.media_storage import MediaError, url_for

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
    row, old_alt = await media_svc.patch_alt(s, media_id=media_id, alt=req.alt)
    if row is None:
        raise HTTPException(404, "media not found")
    await write_event(
        s, type="media.alt_updated", actor=_admin.email,
        target=str(media_id), meta={"id": media_id, "old": old_alt, "new": req.alt},
    )
    await s.commit()
    return _to_item(row)


@router.delete(
    "/media/{media_id}",
    status_code=204,
    dependencies=[Depends(require_scope("write"))],
)
async def delete_media(
    media_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    was_deleted, storage_path, filename = await media_svc.delete_one(
        s, media_id=media_id
    )
    if not was_deleted:
        raise HTTPException(404, "media not found")
    await write_event(
        s, type="media.deleted", actor=_admin.email,
        target=str(media_id),
        meta={"id": media_id, "filename": filename, "storage_path": storage_path},
    )
    await s.commit()

    # File unlink AFTER commit: a crash mid-call leaves an orphan file (cleanable),
    # never a DB row pointing to a missing file.
    if storage_path is not None:
        await media_storage.delete(storage_path)

    return Response(status_code=204)


@router.post(
    "/media",
    response_model=MediaUploadResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def upload_media(
    files: list[UploadFile],
    _admin: Account = Depends(current_admin),
    _s: AsyncSession = Depends(get_session),
) -> MediaUploadResponse:
    ok: list[MediaItem] = []
    failed: list[MediaUploadFailure] = []

    for f in files:
        original = f.filename or "unnamed"
        declared = f.content_type or "application/octet-stream"
        content = await f.read()

        try:
            save_result = await media_storage.save(
                content, declared_mime=declared, original_name=original
            )
        except MediaError as e:
            failed.append(MediaUploadFailure(filename=original, error=str(e)))
            continue

        # Per-file transaction: insert + event_log + commit. If commit fails,
        # we delete the disk write so we don't leak orphans.
        try:
            async with AsyncSessionLocal() as s2:
                try:
                    row = await media_svc.create(
                        s2, save_result=save_result, original_filename=original
                    )
                    await write_event(
                        s2, type="media.uploaded", actor=_admin.email,
                        target=str(row.id),
                        meta={
                            "filename": original,
                            "size": save_result.size,
                            "mime": save_result.mime_type,
                            "width": save_result.width,
                            "height": save_result.height,
                        },
                    )
                    await s2.commit()
                except Exception:
                    await s2.rollback()
                    raise
                item = MediaItem(
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
        except SQLAlchemyError as e:
            await media_storage.delete(save_result.storage_path)
            failed.append(
                MediaUploadFailure(filename=original, error=f"db error: {e}")
            )
            continue

        ok.append(item)

    return MediaUploadResponse(ok=ok, failed=failed)
