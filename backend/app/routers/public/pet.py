"""Pet public endpoint — multi-provider gateway with article context."""
from __future__ import annotations

import json
import random

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal, get_session
from app.models import PetMessage, Post, SiteMeta, Tag
from app.redis import get_redis
from app.schemas.pet import PetConfig, PetMode, PublicPetConfig
from app.services import integrations as integrations_svc
from app.services import pet_assignment, pet_context, pet_gateway, pet_prompt, rate_limit, secret_box
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

log = structlog.get_logger(__name__)
router = APIRouter()


class SummonRequest(BaseModel):
    post_id: str | None = Field(default=None, max_length=64)
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


def _sse(payload: dict) -> str:
    """Format a dict as a single SSE 'data:' frame."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/pet/summon/stream")
async def public_pet_summon_stream(
    req: SummonRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> StreamingResponse:
    """Streaming variant of /pet/summon. Emits SSE frames:

      data: {"type":"meta","mode":"...","species":"..."}
      data: {"type":"chunk","text":"..."}        (one or more)
      data: {"type":"done","source":"<provider>"}
      data: {"type":"fallback","text":"...","source":"fallback"}
      data: {"type":"rate_limited","text":"...","breach":"..."}

    Front-end accumulates `chunk.text` and replaces with `fallback.text`
    or `rate_limited.text` when those terminal events arrive.
    """
    # Front-load all DB reads; the streaming body must not depend on `s`
    # because the dependency-managed session may be closed before the
    # generator finishes flushing chunks.
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
    actor_hash = ip_hash(client_ip_from(request))[:12]
    visitor_hash = ip_hash(client_ip_from(request))[:16]

    if breach is not None:
        quip = random.choice(cfg.tired_lines)
        await write_event(
            s, type="pet.summoned", actor=actor_hash,
            meta={"source": "rate_limited", "breach": breach},
        )
        await s.commit()
        try:
            async with AsyncSessionLocal() as s2:
                m = PetMessage(
                    visitor_hash=visitor_hash, species="unknown",
                    mode="rate_limited",
                    system_prompt="(rate-limited; no LLM call)",
                    prior_turns=[],
                    reply=quip, source="rate_limited",
                )
                s2.add(m)
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_rl", error=repr(e))

        async def rate_limited_stream():
            yield _sse({"type": "rate_limited", "text": quip, "breach": breach})

        return StreamingResponse(rate_limited_stream(), media_type="text/event-stream")

    # Mode + post lookup.
    if not cfg.enable_article_context:
        post_id = None
        selection = None
        mode: PetMode = "greet"
    else:
        post_id = req.post_id
        selection = req.selection
        mode = req.mode or pet_prompt.infer_mode(post_id=post_id, selection=selection)

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

    prior: list[dict] = []
    try:
        prior = await pet_context.load(redis, visitor_hash, max_turns=cfg.context_window_turns)
    except Exception as e:  # noqa: BLE001
        log.warning("pet_summon_stream.ctx_load_failed", error=repr(e))

    messages = pet_prompt.build_messages(
        cfg, mode=mode,
        title=title, tag=tag_label, summary=summary, selection=selection,
        prior=prior,
    )

    # Capture for post-stream Redis append (last item is current user turn).
    current_user_turn = messages[-1].copy()

    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        await write_event(
            s, type="pet.summoned", actor=actor_hash,
            meta={"source": "fallback", "mode": mode, "species": assigned, "stream": True},
        )
        await s.commit()
        try:
            async with AsyncSessionLocal() as s2:
                m = PetMessage(
                    visitor_hash=visitor_hash, species=assigned,
                    mode=mode, post_id=post_id, title=title, tag_slug=tag_label,
                    summary=summary, selection=selection,
                    system_prompt=system, prior_turns=prior,
                    reply=quip, source="fallback",
                )
                s2.add(m)
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_fallback", error=repr(e))

        async def disabled_stream():
            yield _sse({"type": "meta", "mode": mode, "species": assigned})
            yield _sse({"type": "fallback", "text": quip, "source": "fallback"})

        return StreamingResponse(disabled_stream(), media_type="text/event-stream")

    secrets = await _resolve_secrets(s, cfg.providers)
    # Capture immutables for the generator; dropping `s` so we don't depend
    # on session lifetime during chunked send.
    providers = list(cfg.providers)
    fallback_lines = list(cfg.fallback_lines)

    async def event_stream():
        terminal_source = "fallback"
        accumulated_chunks: list[str] = []
        try:
            yield _sse({"type": "meta", "mode": mode, "species": assigned})
            async for evt in pet_gateway.summon_stream(
                providers=providers,
                secrets=secrets,
                system=system,
                messages=messages,
                fallback_lines=fallback_lines,
            ):
                if evt.get("type") == "chunk":
                    accumulated_chunks.append(evt.get("text", ""))
                yield _sse(evt)
                if evt.get("type") in ("done", "fallback"):
                    terminal_source = evt.get("source", "fallback")
                    break
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.error", error=repr(e))
            yield _sse({"type": "error", "message": "stream failed"})

        full_reply = "".join(accumulated_chunks).strip()

        # Update Redis ctx — only for real LLM replies (not fallback).
        if terminal_source not in ("fallback", "rate_limited") and full_reply:
            try:
                await pet_context.append(
                    redis, visitor_hash,
                    user_turn=current_user_turn,
                    assistant_turn={"role": "assistant", "content": full_reply},
                    max_turns=cfg.context_window_turns,
                    ttl_sec=cfg.context_ttl_seconds,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("pet_summon_stream.ctx_append_failed", error=repr(e))

        # Archive every turn (including fallback) to pet_message.
        if full_reply or terminal_source == "fallback":
            archive_reply = full_reply or random.choice(fallback_lines)
            try:
                async with AsyncSessionLocal() as s2:
                    m = PetMessage(
                        visitor_hash=visitor_hash,
                        species=assigned,
                        mode=mode,
                        post_id=post_id,
                        title=title,
                        tag_slug=tag_label,
                        summary=summary,
                        selection=selection,
                        system_prompt=system,
                        prior_turns=prior,
                        reply=archive_reply,
                        source=terminal_source,
                    )
                    s2.add(m)
                    await write_event(
                        s2, type="pet.summoned", actor=actor_hash,
                        meta={
                            "source": terminal_source, "mode": mode,
                            "species": assigned, "stream": True,
                        },
                    )
                    await s2.commit()
            except Exception as e:  # noqa: BLE001
                log.warning("pet_summon_stream.archive_failed", error=repr(e))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
