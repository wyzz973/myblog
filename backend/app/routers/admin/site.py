from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, SiteMeta
from app.services.event_log import write_event

router = APIRouter()


class ProfileIn(BaseModel):
    name: str | None = None
    name_en: str | None = None
    role: str | None = None
    bio: str | None = None
    location: str | None = None
    pronouns: str | None = None
    avatar_path: str | None = None
    typing_line: str | None = None
    stack_chips: list[str] | None = None


class SiteIn(BaseModel):
    handle: str | None = None
    tagline: str | None = None
    email: str | None = None
    github: str | None = None
    footer_note: str | None = None
    default_theme: str | None = None
    launched_at: str | None = None  # ISO date


class ThemeIn(BaseModel):
    accent_color: str | None = None
    accent2_color: str | None = None
    violet_color: str | None = None
    danger_color: str | None = None


async def _fetch(s: AsyncSession) -> SiteMeta:
    sm = (
        await s.execute(select(SiteMeta).where(SiteMeta.id == 1))
    ).scalar_one_or_none()
    if sm is None:
        raise HTTPException(status_code=500, detail="site_meta not seeded")
    return sm


def _apply(sm: SiteMeta, payload: BaseModel) -> None:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sm, k, v)


@router.get("/profile")
async def get_profile(
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    sm = await _fetch(s)
    return {k: getattr(sm, k) for k in ProfileIn.model_fields}


@router.put("/profile", dependencies=[Depends(require_scope("write"))])
async def put_profile(
    payload: ProfileIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    sm = await _fetch(s)
    _apply(sm, payload)
    await write_event(s, type="identity.updated", actor=admin.email)
    return {k: getattr(sm, k) for k in ProfileIn.model_fields}


@router.get("/site")
async def get_site(
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    sm = await _fetch(s)
    return {k: getattr(sm, k) for k in SiteIn.model_fields}


@router.put("/site", dependencies=[Depends(require_scope("write"))])
async def put_site(
    payload: SiteIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    sm = await _fetch(s)
    data = payload.model_dump(exclude_unset=True)
    if "launched_at" in data:
        raw = data.pop("launched_at")
        if raw is not None:
            from datetime import date as date_t

            try:
                sm.launched_at = date_t.fromisoformat(raw)
            except ValueError:
                raise HTTPException(
                    status_code=422, detail="launched_at: ISO date required"
                )
    for k, v in data.items():
        setattr(sm, k, v)
    await write_event(s, type="site.updated", actor=admin.email)
    return {k: getattr(sm, k) for k in SiteIn.model_fields}


@router.get("/theme")
async def get_theme(
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    sm = await _fetch(s)
    return {k: getattr(sm, k) for k in ThemeIn.model_fields}


@router.put("/theme", dependencies=[Depends(require_scope("write"))])
async def put_theme(
    payload: ThemeIn,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    sm = await _fetch(s)
    _apply(sm, payload)
    await write_event(s, type="theme.updated", actor=admin.email)
    return {k: getattr(sm, k) for k in ThemeIn.model_fields}
