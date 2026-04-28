from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.analytics import (
    AnalyticsBundleResponse,
    DashboardResponse,
    PostHitsItem,
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
    days: int = Query(default=30, ge=1, le=365),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[PostHitsItem]:
    return await analytics_svc.per_post(s, days=days, limit=50)


@router.get("/analytics/tags", response_model=list[TagHitsItem])
async def get_analytics_tags(
    days: int = Query(default=30, ge=1, le=365),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[TagHitsItem]:
    return await analytics_svc.per_tag(s, days=days)
