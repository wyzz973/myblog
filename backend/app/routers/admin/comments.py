from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select as _select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, Post, SiteMeta
from app.schemas.comment import (
    AdminCommentItem,
    AdminCommentPatchRequest,
    AdminCommentPatchResponse,
)
from app.services import comments
from app.services.event_log import write_event

router = APIRouter()


@router.get("/comments", response_model=list[AdminCommentItem])
async def list_comments(
    status: Literal["pending", "approved", "spam"] | None = None,
    post_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[AdminCommentItem]:
    rows = await comments.list_admin(
        s, status=status, post_id=post_id, limit=limit, offset=offset
    )
    post_ids = {r.post_id for r in rows}
    titles: dict[str, str] = {}
    if post_ids:
        title_rows = (
            await s.execute(_select(Post.id, Post.title).where(Post.id.in_(post_ids)))
        ).all()
        titles = {pid: title for pid, title in title_rows}
    return [
        AdminCommentItem(
            id=r.id, post_id=r.post_id, post_title=titles.get(r.post_id),
            parent_id=r.parent_id,
            who=r.who, email_hash=r.email_hash, body=r.body,
            status=r.status, flag=r.flag, actor=r.actor, created_at=r.created_at,
        )
        for r in rows
    ]


@router.patch(
    "/comments/{comment_id}",
    response_model=AdminCommentPatchResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def patch_comment(
    comment_id: int,
    req: AdminCommentPatchRequest,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> AdminCommentPatchResponse:
    site = (
        await s.execute(_select(SiteMeta).where(SiteMeta.id == 1))
    ).scalar_one_or_none()
    admin_who = site.name if site else "admin"

    parent, child = await comments.patch(
        s,
        comment_id=comment_id,
        status=req.status,
        flag=req.flag,
        reply_body=req.reply_body,
        admin_who=admin_who,
    )
    if parent is None:
        raise HTTPException(404, "comment not found")
    if req.status is not None:
        await write_event(
            s, type="comment.moderated", actor=_admin.email,
            target=str(parent.id),
            meta={"to_status": req.status},
        )
    if req.flag is not None:
        await write_event(
            s, type="comment.flagged", actor=_admin.email,
            target=str(parent.id),
            meta={"flag": req.flag},
        )
    if child is not None:
        await write_event(
            s, type="comment.replied", actor=_admin.email,
            target=str(parent.id),
            meta={"child_id": child.id, "post_id": parent.post_id},
        )
    await s.commit()
    return AdminCommentPatchResponse(
        id=parent.id,
        status=parent.status,
        flag=parent.flag,
        reply_id=child.id if child else None,
    )


@router.delete("/comments/{comment_id}", status_code=204, dependencies=[Depends(require_scope("write"))])
async def delete_comment(
    comment_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    ok = await comments.delete_one(s, comment_id=comment_id)
    if not ok:
        raise HTTPException(404, "comment not found")
    await write_event(s, type="comment.deleted", actor=_admin.email,
                       meta={"comment_id": comment_id})
    await s.commit()
    return Response(status_code=204)
