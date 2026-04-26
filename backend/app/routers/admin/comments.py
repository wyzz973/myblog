from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account
from app.schemas.comment import AdminCommentItem
from app.services import comments

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
    return [
        AdminCommentItem(
            id=r.id, post_id=r.post_id, parent_id=r.parent_id,
            who=r.who, email_hash=r.email_hash, body=r.body,
            status=r.status, flag=r.flag, actor=r.actor, created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/comments/{comment_id}", status_code=204, dependencies=[Depends(require_scope("write"))])
async def delete_comment(
    comment_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    ok = await comments.delete_one(s, comment_id=comment_id)
    if not ok:
        raise HTTPException(404, "comment not found")
    return Response(status_code=204)
