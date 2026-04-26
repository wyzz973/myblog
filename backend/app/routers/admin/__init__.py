from fastapi import APIRouter

from app.routers.admin.auth import router as auth_router
from app.routers.admin.contacts import router as contacts_router
from app.routers.admin.posts import router as posts_router
from app.routers.admin.projects import router as projects_router
from app.routers.admin.site import router as site_router
from app.routers.admin.tags import router as tags_router

router = APIRouter(prefix="/api/admin")
router.include_router(auth_router, tags=["admin·auth"])
router.include_router(posts_router, tags=["admin·posts"])
router.include_router(tags_router, tags=["admin·tags"])
router.include_router(projects_router, tags=["admin·projects"])
router.include_router(contacts_router, tags=["admin·contacts"])
router.include_router(site_router, tags=["admin·site"])
