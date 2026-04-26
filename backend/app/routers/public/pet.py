import random

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import SiteMeta
from app.redis import get_redis
from app.schemas.pet import PetConfig, PublicPetConfig
from app.services import integrations as integrations_svc
from app.services import pet_llm, rate_limit
from app.services.client_ip import client_ip_key_part

router = APIRouter()


async def _load_pet_config(s: AsyncSession) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


@router.get("/pet/config", response_model=PublicPetConfig)
async def public_pet_config(
    s: AsyncSession = Depends(get_session),
) -> PublicPetConfig:
    cfg = await _load_pet_config(s)
    return PublicPetConfig(
        species=cfg.species, hat=cfg.hat, tint=cfg.tint,
        enabled=cfg.enabled, visitor_can_change=cfg.visitor_can_change,
    )


@router.post("/pet/summon")
async def public_pet_summon(
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    cfg = await _load_pet_config(s)
    ip_key = client_ip_key_part(request)
    await rate_limit.hit(redis, f"rl:pet:{ip_key}", limit=cfg.rate_limit_per_min, window_sec=60)

    api_key = await integrations_svc.get_secret(s, name="anthropic")
    if api_key is None or not cfg.enabled:
        return {"quip": random.choice(cfg.fallback_lines), "source": "fallback"}
    quip, source = await pet_llm.summon(
        api_key=api_key,
        system_prompt=cfg.system_prompt,
        model=cfg.model,
        fallback_lines=cfg.fallback_lines,
    )
    return {"quip": quip, "source": source}
