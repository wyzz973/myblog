"""Pet public endpoint — multi-provider gateway with article context."""
from __future__ import annotations

import random

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, SiteMeta
from app.redis import get_redis
from app.schemas.pet import PetConfig, PublicPetConfig
from app.services import integrations as integrations_svc
from app.services import pet_gateway, rate_limit, secret_box
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

router = APIRouter()


class SummonRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=80)
    selection: str | None = Field(default=None, max_length=4000)


async def _load_pet_config(s: AsyncSession) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.get("/pet/config", response_model=PublicPetConfig)
async def public_pet_config(s: AsyncSession = Depends(get_session)) -> PublicPetConfig:
    cfg = await _load_pet_config(s)
    return PublicPetConfig(
        species=cfg.species, hat=cfg.hat, tint=cfg.tint,
        enabled=cfg.enabled, visitor_can_change=cfg.visitor_can_change,
    )


def _build_prompt(
    cfg: PetConfig,
    *,
    post: Post | None,
    selection: str | None,
) -> tuple[str, str, str]:
    """Returns (system, user, mode)."""
    base_system = cfg.system_prompt
    if selection and post is not None and cfg.enable_article_context:
        explain_system = (
            "You are a tiny ASCII desktop pet that explains technical snippets "
            "in 1 short sentence. Mix English/Chinese naturally. No quotes."
        )
        sel = selection[: cfg.max_context_chars]
        return explain_system, f"From '{post.title}': {sel}", "explain"
    if post is not None and cfg.enable_article_context:
        summary = (post.summary or "")[:200]
        return base_system, f"Comment on this article. Title: {post.title}. Summary: {summary}", "comment"
    return base_system, "summon", "greet"


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

    # Rate limit (3 layers)
    breach = await rate_limit.check_pet(
        redis, ip=ip_key,
        per_ip_per_min=cfg.per_ip_per_min,
        per_ip_per_day=cfg.per_ip_per_day,
        global_per_day=cfg.global_per_day,
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

    # Resolve post
    post: Post | None = None
    if req.post_id:
        post = (await s.execute(select(Post).where(Post.id == req.post_id))).scalar_one_or_none()

    # Build prompt
    system, user, mode = _build_prompt(cfg, post=post, selection=req.selection)

    # Disabled / no providers / no secrets → fallback
    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        source = "fallback"
    else:
        secrets = await _resolve_secrets(s, cfg.providers)
        quip, source = await pet_gateway.summon(
            providers=cfg.providers,
            secrets=secrets,
            system=system,
            user=user,
            fallback_lines=cfg.fallback_lines,
        )

    await write_event(
        s, type="pet.summoned",
        actor=ip_hash(client_ip_from(request))[:12],
        meta={"source": source, "mode": mode},
    )
    await s.commit()
    return {"quip": quip, "source": source, "mode": mode}
