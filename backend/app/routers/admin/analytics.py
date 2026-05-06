import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Post
from app.schemas.analytics import (
    AnalyticsBundleResponse,
    DashboardResponse,
    PostHitsItem,
    PostTimeseriesResponse,
    TagHitsItem,
)
from app.services import analytics as analytics_svc

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await analytics_svc.dashboard_kpis(s)


@router.get("/analytics", response_model=AnalyticsBundleResponse)
async def get_analytics(
    days: int = Query(default=30, ge=1),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> AnalyticsBundleResponse:
    days = min(days, 365)  # clamp upper bound
    return AnalyticsBundleResponse(
        timeseries=await analytics_svc.timeseries(s, days=days),
        top_paths=await analytics_svc.top_paths(s, days=days, limit=10),
        top_referrers=await analytics_svc.top_referrers(s, days=days, limit=10),
        top_countries=await analytics_svc.top_countries(s, days=days, limit=10),
    )


@router.get("/analytics/posts", response_model=list[PostHitsItem])
async def get_analytics_posts(
    days: int = Query(default=30, ge=1),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[PostHitsItem]:
    days = min(days, 365)
    return await analytics_svc.per_post(s, days=days, limit=50)


@router.get("/analytics/tags", response_model=list[TagHitsItem])
async def get_analytics_tags(
    days: int = Query(default=30, ge=1),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[TagHitsItem]:
    days = min(days, 365)
    return await analytics_svc.per_tag(s, days=days)


@router.get(
    "/analytics/posts/{post_id}/timeseries",
    response_model=PostTimeseriesResponse,
)
async def get_analytics_post_timeseries(
    post_id: str,
    days: int = Query(default=30, ge=1),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostTimeseriesResponse:
    """Daily hit timeseries for a single post (Task 25c).

    Returns 404 if the post doesn't exist so the drilldown page can show a
    proper error rather than a confusing all-zero chart.
    """
    days = min(days, 365)
    post = (await s.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    ts = await analytics_svc.per_post_timeseries(s, post_id=post_id, days=days)
    total = sum(p.hits for p in ts)
    return PostTimeseriesResponse(
        post_id=post_id,
        title=post.title,
        total=total,
        timeseries=ts,
    )


# Task 25a: CSV export of per-post hits. The CSV uses BOM-prefixed UTF-8
# so Excel opens it without mojibake; columns are post_id,title,hits.
# Quoting is QUOTE_MINIMAL — only fields containing commas / quotes /
# newlines get wrapped, which keeps small datasets readable.
@router.get("/analytics/posts.csv")
async def get_analytics_posts_csv(
    days: int = Query(default=30, ge=1),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    days = min(days, 365)
    rows = await analytics_svc.per_post(s, days=days, limit=1000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["post_id", "title", "hits"])
    for r in rows:
        writer.writerow([r.post_id, r.title, r.hits])
    body = "﻿" + buf.getvalue()  # UTF-8 BOM for Excel
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"analytics-posts-{stamp}-{days}d.csv"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
