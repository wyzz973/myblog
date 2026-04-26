from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import NotFoundError
from app.models import Post
from app.redis import get_redis
from app.schemas.comment import CommentCreateRequest, CommentCreateResponse
from app.services import comments, rate_limit
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
    ip = request.client.host if request.client else "unknown"
    await rate_limit.hit(redis, f"rl:comment:{ip}", limit=3, window_sec=60)

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
    return CommentCreateResponse(id=row.id, status=row.status)
