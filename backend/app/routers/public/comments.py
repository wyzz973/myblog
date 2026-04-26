from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.errors import NotFoundError
from app.models import Account, Post
from app.redis import get_redis
from app.schemas.comment import (
    CommentCreateRequest,
    CommentCreateResponse,
    PublicAdminReply,
    PublicCommentItem,
)
from app.services import comments, rate_limit
from app.services import email as email_svc
from app.services.client_ip import client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import email_hash

router = APIRouter()


async def _resolve_post(s: AsyncSession, post_id: str) -> Post:
    post = (
        await s.execute(
            select(Post).where(
                Post.id == post_id,
                Post.status == "published",
                Post.private.is_(False),
            )
        )
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("post not found")
    return post


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentCreateResponse,
    status_code=202,
)
async def create_comment(
    post_id: str,
    req: CommentCreateRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> CommentCreateResponse:
    ip_key = client_ip_key_part(request)
    await rate_limit.hit(redis, f"rl:comment:{ip_key}", limit=3, window_sec=60)

    post = await _resolve_post(s, post_id)
    if not post.comments_enabled:
        raise HTTPException(403, "comments disabled on this post")

    row = await comments.create_pending(
        s,
        post_id=post_id,
        who=req.who,
        email_hash=email_hash(req.email),
        body=req.body,
    )

    await write_event(
        s, type="comment.created",
        actor=email_hash(req.email)[:12],
        target=str(row.id),
        meta={"post_id": post_id, "who": req.who, "length": len(req.body)},
    )

    settings = get_settings()
    notify_to = settings.admin_notify_email
    if notify_to is None:
        admin = (
            await s.execute(select(Account).where(Account.id == 1))
        ).scalar_one_or_none()
        notify_to = admin.email if admin else None
    if notify_to:
        await email_svc.send_comment_notification(
            to=notify_to,
            comment_id=row.id,
            post_id=post_id,
            who=req.who,
            snippet=req.body,
        )

    await s.commit()
    return CommentCreateResponse(id=row.id, status=row.status)


@router.get("/posts/{post_id}/comments", response_model=list[PublicCommentItem])
async def list_comments(
    post_id: str,
    s: AsyncSession = Depends(get_session),
) -> list[PublicCommentItem]:
    await _resolve_post(s, post_id)
    pairs = await comments.list_for_post(s, post_id=post_id)
    return [
        PublicCommentItem(
            id=top.id, who=top.who, body=top.body, created_at=top.created_at,
            admin_reply=(
                PublicAdminReply(
                    id=reply.id, who=reply.who, body=reply.body, created_at=reply.created_at
                ) if reply else None
            ),
        )
        for top, reply in pairs
    ]
