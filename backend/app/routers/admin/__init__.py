from fastapi import APIRouter

from app.routers.admin.auth import router as auth_router
from app.routers.admin.posts import router as posts_router

router = APIRouter(prefix="/api/admin")
router.include_router(auth_router, tags=["admin·auth"])
router.include_router(posts_router, tags=["admin·posts"])
