from fastapi import APIRouter

from app.routers.public.health import router as health_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
