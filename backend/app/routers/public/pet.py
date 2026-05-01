"""Pet public endpoint — multi-provider gateway with article context."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, SiteMeta, Tag
from app.redis import get_redis
from app.schemas.pet import PetConfig, PetMode, PublicPetConfig
from app.services import integrations as integrations_svc
from app.services import pet_assignment, pet_gateway, pet_prompt, rate_limit, secret_box
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

router = APIRouter()


class SummonRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=80)
    selection: str | None = Field(default=None, max_length=4000)
    mode: PetMode | None = None


async def _load_pet_config(s: AsyncSession) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.get("/pet/config", response_model=PublicPetConfig)
async def public_pet_config(
    request: Request,
    response: Response,
    s: AsyncSession = Depends(get_session),
) -> PublicPetConfig:
    cfg = await _load_pet_config(s)
    assigned = pet_assignment.verify_cookie(
        request.cookies.get(pet_assignment.COOKIE_NAME)
    )
    if assigned is None:
        assigned = pet_assignment.assign_species(
            ip=client_ip_from(request),
            user_agent=request.headers.get("user-agent"),
        )
        response.set_cookie(
            key=pet_assignment.COOKIE_NAME,
            value=pet_assignment.sign_cookie(assigned),
            max_age=pet_assignment.COOKIE_MAX_AGE,
            path="/",
            samesite="lax",
            httponly=False,
        )
    return PublicPetConfig(
        species=cfg.species,
        assigned_species=assigned,
        hat=cfg.hat, tint=cfg.tint,
        enabled=cfg.enabled, visitor_can_change=cfg.visitor_can_change,
    )


async def _resolve_secrets(s: AsyncSession, providers: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for name in providers:
        row = await integrations_svc.get(s, name=name)
        if row is None:
            continue
        out[name] = {
            "key": secret_box.decrypt(row.secret_encrypted),
            "model": (row.extra_json or {}).get("model"),
        }
    return out


@router.post("/pet/summon")
async def public_pet_summon(
    req: SummonRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    cfg = await _load_pet_config(s)
    ip_key = client_ip_key_part(request)

    breach = await rate_limit.check_pet(
        redis, ip=ip_key,
        per_ip_per_min=cfg.per_ip_per_min,
        per_ip_per_day=cfg.per_ip_per_day,
        global_per_day=cfg.global_per_day,
        unlimited=cfg.unlimited,
        hard_ceiling_per_day=cfg.hard_ceiling_per_day,
    )
    if breach is not None:
        quip = random.choice(cfg.tired_lines)
        await write_event(
            s, type="pet.summoned",
            actor=ip_hash(client_ip_from(request))[:12],
            meta={"source": "rate_limited", "breach": breach},
        )
        await s.commit()
        return {"quip": quip, "source": "rate_limited", "mode": "rate_limited"}

    # Determine mode and load post if relevant.
    if not cfg.enable_article_context:
        # Article context disabled — force greet, ignore post_id/selection.
        post_id = None
        selection = None
        mode: PetMode = "greet"
    else:
        post_id = req.post_id
        selection = req.selection
        mode = req.mode or pet_prompt.infer_mode(post_id=post_id, selection=selection)

    post: Post | None = None
    title: str | None = None
    tag_label: str | None = None
    summary: str | None = None
    if post_id:
        post = (await s.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
        if post is not None:
            title = post.title
            summary = post.summary
            if post.tag_id is not None:
                t = (await s.execute(select(Tag).where(Tag.id == post.tag_id))).scalar_one_or_none()
                tag_label = t.slug if t else None

    # Resolve assigned species (cookie → fingerprint).
    assigned = pet_assignment.verify_cookie(
        request.cookies.get(pet_assignment.COOKIE_NAME)
    ) or pet_assignment.assign_species(
        ip=client_ip_from(request),
        user_agent=request.headers.get("user-agent"),
    )

    system = pet_prompt.build_system(
        cfg, species=assigned, mode=mode,
        title=title, tag=tag_label, summary=summary, selection=selection,
    )

    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        source = "fallback"
    else:
        secrets = await _resolve_secrets(s, cfg.providers)
        quip, source = await pet_gateway.summon(
            providers=cfg.providers,
            secrets=secrets,
            system=system,
            user="summon",
            fallback_lines=cfg.fallback_lines,
        )

    await write_event(
        s, type="pet.summoned",
        actor=ip_hash(client_ip_from(request))[:12],
        meta={"source": source, "mode": mode, "species": assigned},
    )
    await s.commit()
    return {"quip": quip, "source": source, "mode": mode}
