from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine
from app.redis import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.get("/readyz")
async def readyz() -> dict:
    db_ok = False
    redis_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        db_ok = True
    except Exception:
        pass
    try:
        client = get_redis()
        await client.ping()
        await client.aclose()
        redis_ok = True
    except Exception:
        pass

    if db_ok and redis_ok:
        return {"db": True, "redis": True}
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail={"db": db_ok, "redis": redis_ok})
