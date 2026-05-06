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


def resolve_window(
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
) -> tuple[date, date]:
    """Map (days OR [from, to]) → (start_inclusive, end_inclusive).

    Task 25b-arbitrary-end: arbitrary `[from, to]` overrides `days`. When
    only `days` is given, end defaults to today (existing behavior).
    Inputs are clamped to [1, 365] days.
    """
    today = _today_utc()
    if from_ is not None and to is not None:
        if to < from_:
            raise ValueError("`to` must be >= `from`")
        # Cap window length so a misclick doesn't ask for years of data.
        if (to - from_).days > 365:
            raise ValueError("range exceeds 365 days")
        return (from_, to)
    n = max(1, min(days or 30, 365))
    return (today - timedelta(days=n - 1), today)


async def _hits_history_window(
    s: AsyncSession, *, start: date, end_exclusive: date,
) -> dict[date, int]:
    """Sum hit_daily.hits per date in [start, end_exclusive)."""
    res = await s.execute(
        select(HitDaily.date, func.sum(HitDaily.hits))
        .where(HitDaily.date >= start)
        .where(HitDaily.date < end_exclusive)
        .group_by(HitDaily.date)
    )
    return {row[0]: int(row[1] or 0) for row in res.all()}


async def _hits_history(s: AsyncSession, *, days: int) -> dict[date, int]:
    """Backwards-compat wrapper for callers that still pass `days=N`."""
    today = _today_utc()
    return await _hits_history_window(
        s, start=today - timedelta(days=days - 1), end_exclusive=today,
    )


def _window_pieces(
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
) -> tuple[date, date, datetime | None]:
    """Decompose an analytics window into (start, history_end_exclusive,
    today_start_dt_or_None). Today's HitEvent live-add is included only
    when the window actually covers today (end >= today). Otherwise the
    aggregate is fully historical and the caller skips the live branch.
    """
    today = _today_utc()
    start, end = resolve_window(days=days, from_=from_, to=to)
    if end >= today:
        return start, today, _today_start_utc()
    return start, end + timedelta(days=1), None


async def timeseries(
    s: AsyncSession,
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
) -> list[DayPoint]:
    """Daily hit timeseries.

    Two calling conventions:
      - `days=N` (legacy) → window = last N days ending today
      - `from_=D1, to=D2`  → window = [D1, D2] inclusive (Task 25b-arbitrary-end)

    The right edge of the window contributes today's live hit_events count
    only when `to == today`; otherwise the window is fully historical.
    """
    today = _today_utc()
    start, end = resolve_window(days=days, from_=from_, to=to)

    # History rows cover [start, end_exclusive_for_history) where
    # end_exclusive_for_history = end + 1 if end < today else today
    history_end_exclusive = end + timedelta(days=1) if end < today else today
    history = await _hits_history_window(
        s, start=start, end_exclusive=history_end_exclusive,
    )
    today_hits = await _hits_today(s) if end >= today else 0

    points: list[DayPoint] = []
    n_days = (end - start).days + 1
    for i in range(n_days):
        d = start + timedelta(days=i)
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
    s: AsyncSession,
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
    limit: int = 10,
) -> list[PathHits]:
    start, history_end_exclusive, today_start_dt = _window_pieces(
        days=days, from_=from_, to=to,
    )
    history = await s.execute(
        select(HitDaily.path, func.sum(HitDaily.hits).label("h"))
        .where(HitDaily.date >= start).where(HitDaily.date < history_end_exclusive)
        .group_by(HitDaily.path)
    )
    counts: dict[str, int] = {p: int(h or 0) for p, h in history.all()}
    if today_start_dt is not None:
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
    s: AsyncSession,
    *,
    column,
    key: str,
    start: date,
    history_end_exclusive: date,
) -> dict[str, int]:
    res = await s.execute(
        select(column)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < history_end_exclusive)
    )
    counts: dict[str, int] = {}
    for (arr,) in res.all():
        if not arr:
            continue
        for item in arr:
            counts[item[key]] = counts.get(item[key], 0) + int(item["n"])
    return counts


async def top_referrers(
    s: AsyncSession,
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
    limit: int = 10,
) -> list[ReferrerHits]:
    start, history_end_exclusive, today_start_dt = _window_pieces(
        days=days, from_=from_, to=to,
    )
    counts = await _merge_jsonb_top(
        s, column=HitDaily.referrers_top, key="r",
        start=start, history_end_exclusive=history_end_exclusive,
    )
    if today_start_dt is not None:
        today_rows = await s.execute(
            select(HitEvent.referrer, func.count(HitEvent.id))
            .where(HitEvent.created_at >= today_start_dt)
            .where(HitEvent.referrer.isnot(None))
            .group_by(HitEvent.referrer)
        )
        for r, n in today_rows.all():
            counts[r] = counts.get(r, 0) + int(n or 0)
    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [ReferrerHits(referrer=r, hits=n) for r, n in sorted_pairs]


async def top_countries(
    s: AsyncSession,
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
    limit: int = 10,
) -> list[CountryHits]:
    start, history_end_exclusive, today_start_dt = _window_pieces(
        days=days, from_=from_, to=to,
    )
    counts = await _merge_jsonb_top(
        s, column=HitDaily.countries_top, key="c",
        start=start, history_end_exclusive=history_end_exclusive,
    )
    if today_start_dt is not None:
        today_rows = await s.execute(
            select(HitEvent.country, func.count(HitEvent.id))
            .where(HitEvent.created_at >= today_start_dt)
            .where(HitEvent.country.isnot(None))
            .group_by(HitEvent.country)
        )
        for c, n in today_rows.all():
            counts[c] = counts.get(c, 0) + int(n or 0)
    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [CountryHits(country=c, hits=n) for c, n in sorted_pairs]


async def per_post(
    s: AsyncSession,
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
    limit: int = 50,
) -> list[PostHitsItem]:
    start, history_end_exclusive, today_start_dt = _window_pieces(
        days=days, from_=from_, to=to,
    )
    history = await s.execute(
        select(
            HitDaily.post_id, Post.title, func.sum(HitDaily.hits).label("h"),
        )
        .join(Post, Post.id == HitDaily.post_id)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < history_end_exclusive)
        .where(HitDaily.post_id.isnot(None))
        .group_by(HitDaily.post_id, Post.title)
    )
    counts: dict[str, tuple[str, int]] = {}
    for post_id, title, h in history.all():
        counts[post_id] = (title, int(h or 0))
    if today_start_dt is not None:
        today_rows = await s.execute(
            select(HitEvent.post_id, Post.title, func.count(HitEvent.id))
            .join(Post, Post.id == HitEvent.post_id)
            .where(HitEvent.created_at >= today_start_dt)
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


async def per_post_timeseries(
    s: AsyncSession, *, post_id: str, days: int
) -> list[DayPoint]:
    """Daily hit timeseries for a single post (Task 25c).

    Combines pre-rolled hit_daily rows for past days with today's live
    hit_events count, identical strategy to ``timeseries`` but filtered to
    one post_id. Returns exactly ``days`` points in ascending date order.
    """
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    history = await s.execute(
        select(HitDaily.date, func.sum(HitDaily.hits))
        .where(HitDaily.date >= start)
        .where(HitDaily.date < today)
        .where(HitDaily.post_id == post_id)
        .group_by(HitDaily.date)
    )
    by_date: dict[date, int] = {row[0]: int(row[1] or 0) for row in history.all()}

    today_n_row = await s.execute(
        select(func.count(HitEvent.id))
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.post_id == post_id)
    )
    today_n = int(today_n_row.scalar() or 0)

    points: list[DayPoint] = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        n = today_n if d == today else by_date.get(d, 0)
        points.append(DayPoint(date=d, hits=n))
    return points


async def per_tag(
    s: AsyncSession,
    *,
    days: int | None = None,
    from_: date | None = None,
    to: date | None = None,
) -> list[TagHitsItem]:
    start, history_end_exclusive, today_start_dt = _window_pieces(
        days=days, from_=from_, to=to,
    )
    history = await s.execute(
        select(
            Tag.id, Tag.slug, Tag.name, func.sum(HitDaily.hits).label("h"),
        )
        .join(Post, Post.id == HitDaily.post_id)
        .join(Tag, Tag.id == Post.tag_id)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < history_end_exclusive)
        .group_by(Tag.id, Tag.slug, Tag.name)
    )
    counts: dict[int, tuple[str, str, int]] = {}
    for tid, slug, name, h in history.all():
        counts[tid] = (slug, name, int(h or 0))
    if today_start_dt is not None:
        today_rows = await s.execute(
            select(Tag.id, Tag.slug, Tag.name, func.count(HitEvent.id))
            .join(Post, Post.id == HitEvent.post_id)
            .join(Tag, Tag.id == Post.tag_id)
            .where(HitEvent.created_at >= today_start_dt)
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
