from fastapi import APIRouter

from app.routers.public.health import router as health_router
from app.routers.public.site import router as site_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
router.include_router(site_router, tags=["site"])
