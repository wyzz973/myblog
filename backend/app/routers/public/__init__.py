from fastapi import APIRouter

from app.routers.public.contacts import router as contacts_router
from app.routers.public.contrib import router as contrib_router
from app.routers.public.health import router as health_router
from app.routers.public.posts import router as posts_router
from app.routers.public.projects import router as projects_router
from app.routers.public.site import router as site_router
from app.routers.public.tags import router as tags_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
router.include_router(site_router, tags=["site"])
router.include_router(contacts_router, tags=["public"])
router.include_router(tags_router, tags=["public"])
router.include_router(projects_router, tags=["public"])
router.include_router(posts_router, tags=["public"])
router.include_router(contrib_router, tags=["public"])
