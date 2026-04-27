from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
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
    existing = await media_svc.get(s, media_id=media_id)
    if existing is None:
        raise HTTPException(404, "media not found")
    filename = existing.filename
    was_deleted, storage_path = await media_svc.delete_one(s, media_id=media_id)
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
        from app.services.media_storage import delete as fs_delete
        await fs_delete(storage_path)

    return Response(status_code=204)


@router.post(
    "/media",
    response_model=MediaUploadResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def upload_media(
    files: list[UploadFile],
    _admin: Account = Depends(current_admin),
) -> MediaUploadResponse:
    from app.services import media_storage

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
        except Exception as e:  # noqa: BLE001
            failed.append(
                MediaUploadFailure(filename=original, error=f"internal: {e}")
            )
            continue

        # Per-file transaction: insert + event_log + commit. If commit fails,
        # roll back the disk write so we don't leak orphans.
        try:
            async with AsyncSessionLocal() as s2:
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
                row_id = row.id
                row_filename = row.filename
                row_mime = row.mime_type
                row_size = row.size
                row_w = row.width
                row_h = row.height
                row_alt = row.alt
                row_created = row.created_at
                row_storage = row.storage_path
        except Exception as e:  # noqa: BLE001
            await media_storage.delete(save_result.storage_path)
            failed.append(
                MediaUploadFailure(filename=original, error=f"db error: {e}")
            )
            continue

        ok.append(
            MediaItem(
                id=row_id,
                filename=row_filename,
                url=url_for(row_storage),
                mime_type=row_mime,
                size=row_size,
                width=row_w,
                height=row_h,
                alt=row_alt,
                created_at=row_created,
            )
        )

    return MediaUploadResponse(ok=ok, failed=failed)
