from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import NotFoundError
from app.models import Post, Tag
from app.redis import get_redis
from app.schemas.like import LikeResponse
from app.schemas.post import PostDetail, PostList, PostSummary
from app.services import likes, rate_limit
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

router = APIRouter()


def _summary_from_row(p: Post) -> PostSummary:
    return PostSummary(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
    )


@router.get("/posts", response_model=PostList)
async def list_posts(
    tag: str | None = Query(None),
    q: str | None = Query(None, min_length=1, max_length=100),
    lang: str | None = Query(None, pattern="^(zh|en)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    s: AsyncSession = Depends(get_session),
) -> PostList:
    stmt = select(Post).join(Tag).where(Post.status == "published", Post.private.is_(False))
    if tag and tag != "all":
        stmt = stmt.where(Tag.slug == tag)
    if lang:
        stmt = stmt.where(Post.lang == lang)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Post.title.ilike(like), Post.summary.ilike(like), Post.body_md.ilike(like))
        )
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await s.execute(stmt.order_by(Post.date.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return PostList(
        items=[_summary_from_row(p) for p in rows],
        total=int(total), limit=limit, offset=offset,
    )


@router.get("/posts/{post_id}", response_model=PostDetail)
async def get_post(post_id: str, s: AsyncSession = Depends(get_session)) -> PostDetail:
    post = (await s.execute(
        select(Post).join(Tag).where(
            Post.id == post_id, Post.status == "published", Post.private.is_(False)
        )
    )).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostDetail(
        id=post.id, n=post.n, title=post.title, subtitle=post.subtitle, tag=post.tag.slug,
        date=post.date, read=post.read, lang=post.lang, summary=post.summary,
        tldr=post.tldr, body=post.body_json,
        likes=await likes.get_count(s, post_id=post.id),
        word_count=post.word_count,
    )


@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def like_post(
    post_id: str,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> LikeResponse:
    ip_key = client_ip_key_part(request)
    await rate_limit.hit(redis, f"rl:like:{ip_key}:{post_id}", limit=10, window_sec=60)
    raw_ip = client_ip_from(request)

    # Resolve published+public post
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

    total, was_new = await likes.record_like(s, post_id=post_id, ip=raw_ip)
    if was_new:
        await write_event(
            s,
            type="post.liked",
            actor=ip_hash(raw_ip)[:12],
            target=post_id,
            meta={"day": datetime.now(UTC).date().isoformat()},
        )
    await s.commit()
    return LikeResponse(likes=total, was_new=was_new)
