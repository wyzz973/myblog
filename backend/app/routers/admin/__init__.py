from fastapi import APIRouter

from app.routers.admin.auth import router as auth_router

router = APIRouter(prefix="/api/admin")
router.include_router(auth_router, tags=["admin·auth"])
