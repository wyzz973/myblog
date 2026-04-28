from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.analytics import DashboardResponse
from app.services import analytics as analytics_svc

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await analytics_svc.dashboard_kpis(s)
