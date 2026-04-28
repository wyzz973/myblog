from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.redis import get_redis
from app.schemas.analytics import HitRequest
from app.services import hits as hits_svc

router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "") or ""


@router.post("/hit", status_code=204)
async def record_hit(
    req: HitRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> Response:
    ip = _client_ip(request)
    country = (request.headers.get("CF-IPCountry") or "").upper() or None
    user_agent = request.headers.get("User-Agent")

    await hits_svc.record(
        s,
        redis=redis,
        path=req.path,
        referrer=req.referrer,
        ip=ip,
        country=country,
        user_agent=user_agent,
        post_id=req.post_id,
    )
    await s.commit()
    return Response(status_code=204)
