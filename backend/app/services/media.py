"""Media DB service. Service flushes; routers commit (P4 atomicity invariant)."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Media, Post, SiteMeta
from app.services.media_storage import SaveResult


async def list_all(s: AsyncSession, *, limit: int = 100) -> list[Media]:
    return list(
        (
            await s.execute(
                select(Media).order_by(Media.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def get(s: AsyncSession, *, media_id: int) -> Media | None:
    return (
        await s.execute(select(Media).where(Media.id == media_id))
    ).scalar_one_or_none()


async def create(
    s: AsyncSession,
    *,
    save_result: SaveResult,
    original_filename: str,
    alt: str | None = None,
) -> Media:
    row = Media(
        filename=original_filename,
        storage_path=save_result.storage_path,
        mime_type=save_result.mime_type,
        size=save_result.size,
        width=save_result.width,
        height=save_result.height,
        alt=alt,
        created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def patch_alt(
    s: AsyncSession, *, media_id: int, alt: str | None
) -> tuple[Media | None, str | None]:
    """Update alt text. Returns (row, old_alt). row is None if not found."""
    row = await get(s, media_id=media_id)
    if row is None:
        return None, None
    old_alt = row.alt
    row.alt = alt
    await s.flush()
    await s.refresh(row)
    return row, old_alt


async def delete_one(
    s: AsyncSession, *, media_id: int
) -> tuple[bool, str | None, str | None]:
    """Returns (was_deleted, storage_path, filename).
    Caller commits the row delete first, THEN unlinks the file —
    so a crash leaves an orphan file (cleanable later) instead of a row pointing at nothing."""
    row = await get(s, media_id=media_id)
    if row is None:
        return False, None, None
    storage_path, filename = row.storage_path, row.filename
    await s.execute(delete(Media).where(Media.id == media_id))
    await s.flush()
    return True, storage_path, filename


async def references(s: AsyncSession, *, media_id: int) -> dict:
    """Return where a media item is currently embedded.

    Scans `posts.body_md` for `/media/<storage_path>` substrings (the URL
    shape produced by `url_for(storage_path)`) and checks
    `site_meta.avatar_id`. Used by the delete handler to refuse with 409
    when the media is still in use.
    """
    row = await get(s, media_id=media_id)
    if row is None:
        return {"posts": [], "avatar": False}
    needle = f"/media/{row.storage_path}"
    # Posts.body_md scan — small enough table that LIKE on every row is fine.
    res = await s.execute(
        select(Post.id).where(Post.body_md.like(f"%{needle}%")).order_by(Post.id)
    )
    post_ids = [pid for (pid,) in res.all()]
    # Avatar reverse lookup.
    res2 = await s.execute(
        select(SiteMeta.avatar_id).where(SiteMeta.avatar_id == media_id).limit(1)
    )
    is_avatar = res2.scalar_one_or_none() is not None
    return {"posts": post_ids, "avatar": is_avatar}
