from fastapi import APIRouter

from app.routers.admin.account import router as account_router
from app.routers.admin.activity import router as activity_router
from app.routers.admin.analytics import router as analytics_router
from app.routers.admin.api_tokens import router as api_tokens_router
from app.routers.admin.auth import router as auth_router
from app.routers.admin.comments import router as comments_router
from app.routers.admin.contacts import router as contacts_router
from app.routers.admin.danger import router as danger_router
from app.routers.admin.integrations import router as integrations_router
from app.routers.admin.media import router as media_router
from app.routers.admin.now import router as now_admin_router
from app.routers.admin.pet import router as pet_admin_router
from app.routers.admin.pet_species import router as pet_species_admin_router
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
router.include_router(account_router, tags=["admin·account"])
router.include_router(api_tokens_router, tags=["admin·api-tokens"])
router.include_router(comments_router, tags=["admin·comments"])
router.include_router(activity_router, tags=["admin·activity"])
router.include_router(integrations_router, tags=["admin·integrations"])
router.include_router(pet_admin_router, tags=["admin·pet"])
router.include_router(pet_species_admin_router, tags=["admin·pet·species"])
router.include_router(now_admin_router, tags=["admin·now"])
router.include_router(media_router, tags=["admin·media"])
router.include_router(analytics_router, tags=["admin·analytics"])
router.include_router(danger_router, tags=["admin·danger"])
