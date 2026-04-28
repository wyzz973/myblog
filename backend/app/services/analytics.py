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
    Tag,
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


async def top_paths(
    s: AsyncSession, *, days: int, limit: int = 10
) -> list[PathHits]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)
    today_start_dt = _today_start_utc()

    # Historical days from hit_daily.
    history = await s.execute(
        select(HitDaily.path, func.sum(HitDaily.hits).label("h"))
        .where(HitDaily.date >= start).where(HitDaily.date < today)
        .group_by(HitDaily.path)
    )
    counts: dict[str, int] = {p: int(h or 0) for p, h in history.all()}

    # Today's contribution from hit_events.
    today_rows = await s.execute(
        select(HitEvent.path, func.count(HitEvent.id))
        .where(HitEvent.created_at >= today_start_dt)
        .group_by(HitEvent.path)
    )
    for p, n in today_rows.all():
        counts[p] = counts.get(p, 0) + int(n or 0)

    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [PathHits(path=p, hits=n) for p, n in sorted_pairs]


async def _merge_jsonb_top(
    s: AsyncSession, *, column, key: str, days: int
) -> dict[str, int]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)
    res = await s.execute(
        select(column).where(HitDaily.date >= start).where(HitDaily.date < today)
    )
    counts: dict[str, int] = {}
    for (arr,) in res.all():
        if not arr:
            continue
        for item in arr:
            counts[item[key]] = counts.get(item[key], 0) + int(item["n"])
    return counts


async def top_referrers(
    s: AsyncSession, *, days: int, limit: int = 10
) -> list[ReferrerHits]:
    counts = await _merge_jsonb_top(
        s, column=HitDaily.referrers_top, key="r", days=days
    )
    # Today's contribution from hit_events.
    today_rows = await s.execute(
        select(HitEvent.referrer, func.count(HitEvent.id))
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.referrer.isnot(None))
        .group_by(HitEvent.referrer)
    )
    for r, n in today_rows.all():
        counts[r] = counts.get(r, 0) + int(n or 0)
    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [ReferrerHits(referrer=r, hits=n) for r, n in sorted_pairs]


async def top_countries(
    s: AsyncSession, *, days: int, limit: int = 10
) -> list[CountryHits]:
    counts = await _merge_jsonb_top(
        s, column=HitDaily.countries_top, key="c", days=days
    )
    today_rows = await s.execute(
        select(HitEvent.country, func.count(HitEvent.id))
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.country.isnot(None))
        .group_by(HitEvent.country)
    )
    for c, n in today_rows.all():
        counts[c] = counts.get(c, 0) + int(n or 0)
    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [CountryHits(country=c, hits=n) for c, n in sorted_pairs]


async def per_post(
    s: AsyncSession, *, days: int, limit: int = 50
) -> list[PostHitsItem]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    # Historical sums from hit_daily, JOIN posts for title.
    history = await s.execute(
        select(
            HitDaily.post_id, Post.title, func.sum(HitDaily.hits).label("h"),
        )
        .join(Post, Post.id == HitDaily.post_id)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < today)
        .where(HitDaily.post_id.isnot(None))
        .group_by(HitDaily.post_id, Post.title)
    )
    counts: dict[str, tuple[str, int]] = {}
    for post_id, title, h in history.all():
        counts[post_id] = (title, int(h or 0))

    # Today's contribution from hit_events with post_id.
    today_rows = await s.execute(
        select(HitEvent.post_id, Post.title, func.count(HitEvent.id))
        .join(Post, Post.id == HitEvent.post_id)
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.post_id.isnot(None))
        .group_by(HitEvent.post_id, Post.title)
    )
    for post_id, title, n in today_rows.all():
        prev_title, prev = counts.get(post_id, (title, 0))
        counts[post_id] = (prev_title, prev + int(n or 0))

    sorted_items = sorted(counts.items(), key=lambda kv: kv[1][1], reverse=True)[:limit]
    return [
        PostHitsItem(post_id=pid, title=title, hits=n)
        for pid, (title, n) in sorted_items
    ]


async def per_tag(s: AsyncSession, *, days: int) -> list[TagHitsItem]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    history = await s.execute(
        select(
            Tag.id, Tag.slug, Tag.name, func.sum(HitDaily.hits).label("h"),
        )
        .join(Post, Post.id == HitDaily.post_id)
        .join(Tag, Tag.id == Post.tag_id)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < today)
        .group_by(Tag.id, Tag.slug, Tag.name)
    )
    counts: dict[int, tuple[str, str, int]] = {}
    for tid, slug, name, h in history.all():
        counts[tid] = (slug, name, int(h or 0))

    today_rows = await s.execute(
        select(Tag.id, Tag.slug, Tag.name, func.count(HitEvent.id))
        .join(Post, Post.id == HitEvent.post_id)
        .join(Tag, Tag.id == Post.tag_id)
        .where(HitEvent.created_at >= _today_start_utc())
        .group_by(Tag.id, Tag.slug, Tag.name)
    )
    for tid, slug, name, n in today_rows.all():
        prev_slug, prev_name, prev = counts.get(tid, (slug, name, 0))
        counts[tid] = (prev_slug, prev_name, prev + int(n or 0))

    sorted_items = sorted(counts.items(), key=lambda kv: kv[1][2], reverse=True)
    return [
        TagHitsItem(tag_id=tid, slug=s_, name=n_, hits=h_)
        for tid, (s_, n_, h_) in sorted_items
    ]
