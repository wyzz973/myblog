"""Analytics read service. Today's hits come from hit_events (live);
historical days come from hit_daily."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Comment,
    HitDaily,
    HitEvent,
    LikeEvent,
    Media,
    Post,
)
from app.schemas.analytics import (
    CommentsKPI,
    CountryHits,
    DashboardResponse,
    DayPoint,
    HitsKPI,
    LikesKPI,
    MediaKPI,
    PathHits,
    PostHitsItem,
    PostsKPI,
    ReferrerHits,
    TagHitsItem,
)


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _today_start_utc() -> datetime:
    return datetime.combine(_today_utc(), datetime.min.time(), tzinfo=UTC)


async def _hits_today(s: AsyncSession) -> int:
    res = await s.execute(
        select(func.count(HitEvent.id)).where(HitEvent.created_at >= _today_start_utc())
    )
    return int(res.scalar() or 0)


async def _hits_history(s: AsyncSession, *, days: int) -> dict[date, int]:
    """Sum hit_daily.hits per date for last `days` excluding today."""
    today = _today_utc()
    start = today - timedelta(days=days - 1)
    end_exclusive = today  # everything before today
    res = await s.execute(
        select(HitDaily.date, func.sum(HitDaily.hits))
        .where(HitDaily.date >= start)
        .where(HitDaily.date < end_exclusive)
        .group_by(HitDaily.date)
    )
    return {row[0]: int(row[1] or 0) for row in res.all()}


async def timeseries(s: AsyncSession, *, days: int) -> list[DayPoint]:
    today = _today_utc()
    history = await _hits_history(s, days=days)
    today_hits = await _hits_today(s)

    points: list[DayPoint] = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        n = today_hits if d == today else history.get(d, 0)
        points.append(DayPoint(date=d, hits=n))
    return points


async def dashboard_kpis(s: AsyncSession) -> DashboardResponse:
    # hits — today live + last_7d/last_30d sums
    today = _today_utc()
    today_hits = await _hits_today(s)

    async def _sum_history(days: int) -> int:
        start = today - timedelta(days=days - 1)
        end_exclusive = today
        res = await s.execute(
            select(func.coalesce(func.sum(HitDaily.hits), 0))
            .where(HitDaily.date >= start)
            .where(HitDaily.date < end_exclusive)
        )
        return int(res.scalar() or 0)

    last_7d = today_hits + await _sum_history(7)
    last_30d = today_hits + await _sum_history(30)

    # likes
    likes_total = int((await s.execute(select(func.count(LikeEvent.id)))).scalar() or 0)
    seven_ago = today - timedelta(days=7)
    likes_7 = int((await s.execute(
        select(func.count(LikeEvent.id)).where(LikeEvent.day >= seven_ago)
    )).scalar() or 0)

    # comments
    comments_total = int((await s.execute(select(func.count(Comment.id)))).scalar() or 0)
    comments_pending = int((await s.execute(
        select(func.count(Comment.id)).where(Comment.status == "pending")
    )).scalar() or 0)

    # posts
    async def _count_posts(status: str) -> int:
        return int((await s.execute(
            select(func.count(Post.id)).where(Post.status == status)
        )).scalar() or 0)

    posts_published = await _count_posts("published")
    posts_draft = await _count_posts("draft")
    posts_scheduled = await _count_posts("scheduled")

    # media
    media_count = int((await s.execute(select(func.count(Media.id)))).scalar() or 0)

    return DashboardResponse(
        hits=HitsKPI(today=today_hits, last_7d=last_7d, last_30d=last_30d),
        likes=LikesKPI(total=likes_total, last_7d=likes_7),
        comments=CommentsKPI(total=comments_total, pending=comments_pending),
        posts=PostsKPI(
            published=posts_published, draft=posts_draft, scheduled=posts_scheduled
        ),
        media=MediaKPI(count=media_count),
    )
