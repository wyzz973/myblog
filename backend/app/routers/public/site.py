from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ContribDay, Post, SiteMeta
from app.schemas.site import ProfilePayload, SitePayload

router = APIRouter()


def _format_uptime(launched: date) -> str:
    days = (date.today() - launched).days
    years, rest = divmod(days, 365)
    return f"{years}y {rest}d"


@router.get("/site", response_model=SitePayload)
async def get_site(s: AsyncSession = Depends(get_session)) -> SitePayload:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    posts_count = (await s.execute(
        select(func.count()).select_from(Post).where(Post.status == "published")
    )).scalar_one()
    words = (await s.execute(
        select(func.coalesce(func.sum(Post.word_count), 0)).where(Post.status == "published")
    )).scalar_one()
    commits52w = (await s.execute(
        select(func.coalesce(func.sum(ContribDay.count), 0))
    )).scalar_one() or 1384  # seed fallback when contrib_days is empty

    return SitePayload(
        handle=sm.handle, name=sm.name, name_en=sm.name_en, role=sm.role,
        tagline=sm.tagline, bio=sm.bio, location=sm.location,
        email=sm.email, github=sm.github, pronouns=sm.pronouns,
        uptime=_format_uptime(sm.launched_at),
        posts=int(posts_count), words=int(words), commits52w=int(commits52w),
        footer_note=sm.footer_note,
        default_theme=sm.default_theme,
        accent_color=sm.accent_color, accent2_color=sm.accent2_color,
        violet_color=sm.violet_color, danger_color=sm.danger_color,
        typing_line=sm.typing_line, stack_chips=sm.stack_chips,
    )


@router.get("/profile", response_model=ProfilePayload)
async def get_profile(s: AsyncSession = Depends(get_session)) -> ProfilePayload:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    return ProfilePayload(
        name=sm.name, name_en=sm.name_en, role=sm.role, bio=sm.bio,
        location=sm.location, pronouns=sm.pronouns, avatar_path=sm.avatar_path,
        typing_line=sm.typing_line, stack_chips=sm.stack_chips,
    )
