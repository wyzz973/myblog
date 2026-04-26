"""Comments service: pending-by-default public submission, admin-side
moderation including reply-as-child-comment."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment


async def create_pending(
    s: AsyncSession,
    *,
    post_id: str,
    who: str,
    email_hash: str,
    body: str,
) -> Comment:
    row = Comment(
        post_id=post_id,
        parent_id=None,
        who=who,
        email_hash=email_hash,
        body=body,
        status="pending",
        flag=False,
        actor="public",
        created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.commit()
    await s.refresh(row)
    return row


async def list_for_post(s: AsyncSession, *, post_id: str) -> list[tuple[Comment, Comment | None]]:
    """Return [(top_level, admin_reply_or_None)] in created_at order.

    Top-level comments: status='approved' AND parent_id IS NULL AND post_id=$1.
    Admin reply (≤1 per parent): actor='admin' AND status='approved' AND parent_id=parent.id.
    """
    tops = (
        await s.execute(
            select(Comment)
            .where(
                Comment.post_id == post_id,
                Comment.status == "approved",
                Comment.parent_id.is_(None),
            )
            .order_by(Comment.created_at)
        )
    ).scalars().all()

    if not tops:
        return []

    parent_ids = [t.id for t in tops]
    replies = (
        await s.execute(
            select(Comment).where(
                Comment.parent_id.in_(parent_ids),
                Comment.actor == "admin",
                Comment.status == "approved",
            )
        )
    ).scalars().all()
    by_parent: dict[int, Comment] = {r.parent_id: r for r in replies if r.parent_id}
    return [(t, by_parent.get(t.id)) for t in tops]


async def list_admin(
    s: AsyncSession,
    *,
    status: Literal["pending", "approved", "spam"] | None = None,
    post_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Comment]:
    q = select(Comment)
    if status is not None:
        q = q.where(Comment.status == status)
    if post_id is not None:
        q = q.where(Comment.post_id == post_id)
    q = q.order_by(Comment.created_at.desc()).limit(limit).offset(offset)
    return list((await s.execute(q)).scalars().all())


async def patch(
    s: AsyncSession,
    *,
    comment_id: int,
    status: Literal["pending", "approved", "spam"] | None,
    flag: bool | None,
    reply_body: str | None,
    admin_who: str,
) -> tuple[Comment, Comment | None]:
    """Returns (parent_after_update, child_reply_or_None)."""
    parent = (
        await s.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()
    if parent is None:
        return None, None  # caller raises 404

    if status is not None:
        parent.status = status
    if flag is not None:
        parent.flag = flag

    child: Comment | None = None
    if reply_body is not None:
        child = Comment(
            post_id=parent.post_id,
            parent_id=parent.id,
            who=admin_who,
            email_hash=None,
            body=reply_body,
            status="approved",
            flag=False,
            actor="admin",
            created_at=datetime.now(UTC),
        )
        s.add(child)
    await s.commit()
    if child is not None:
        await s.refresh(child)
    await s.refresh(parent)
    return parent, child


async def delete_one(s: AsyncSession, *, comment_id: int) -> bool:
    res = await s.execute(delete(Comment).where(Comment.id == comment_id))
    await s.commit()
    return res.rowcount > 0
