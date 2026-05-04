"""Pet public endpoint — multi-provider gateway with article context."""
from __future__ import annotations

import asyncio
import json
import random

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal, get_session
from app.models import PetMessage, PetUsageEvent, PetVisitorProfile, Post, SiteMeta, Tag
from app.redis import get_redis
from app.schemas.pet import PetConfig, PetMode, PublicPetConfig, SummonRequest
from app.services import integrations as integrations_svc
from app.services import (
    pet_archive,
    pet_assignment,
    pet_cache,
    pet_context,
    pet_gateway,
    pet_identity,
    pet_profiles,
    pet_prompt,
    pet_usage,
    rate_limit,
    secret_box,
)
from app.services.client_ip import client_ip_from, client_ip_key_part
from app.services.event_log import write_event
from app.services.hashing import ip_hash

log = structlog.get_logger(__name__)
router = APIRouter()


async def _load_pet_config(s: AsyncSession) -> PetConfig:
    site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    raw = site.pet_config or {}
    return PetConfig(**{**PetConfig().model_dump(), **raw})


def _set_vid_cookie(response: Response | StreamingResponse, signed_vid: str) -> None:
    response.set_cookie(
        key=pet_identity.COOKIE_NAME,
        value=signed_vid,
        max_age=pet_identity.COOKIE_MAX_AGE,
        path="/",
        samesite="lax",
        httponly=False,
    )


def _client_locale(req: SummonRequest) -> str | None:
    return req.client_context.locale if req.client_context else None


def _feature_disabled(cfg: PetConfig, mode: str) -> bool:
    if mode in ("free_chat", "follow_up") and not cfg.enable_free_chat:
        return True
    if mode in ("article_finished", "reading_assist", "code_assist") and not cfg.enable_proactive:
        return True
    return False


def _fallback_level(source: str, *, cache_hit: bool = False) -> str:
    if cache_hit:
        return "L1"
    if source == "fallback":
        return "L3"
    if source == "rate_limited":
        return "L3"
    if source == "disabled":
        return "L2"
    return "none"


def _clean_context(req: SummonRequest) -> dict | None:
    if not req.client_context:
        return None
    return pet_prompt.serialize_context(req.client_context)


async def _record_usage_and_archive(
    s: AsyncSession,
    *,
    visitor_hash: str,
    species: str,
    mode: str,
    post_id: str | None,
    title: str | None,
    tag_label: str | None,
    summary: str | None,
    selection: str | None,
    message: str | None,
    intent: str | None,
    client_context: dict | None,
    system: str,
    prior: list[dict],
    reply: str,
    source: str,
    usage: dict[str, int],
    cache_hit: bool = False,
) -> None:
    fallback_level = _fallback_level(source, cache_hit=cache_hit)
    m = PetMessage(
        visitor_hash=visitor_hash,
        species=species,
        mode=mode,
        post_id=post_id,
        title=title,
        tag_slug=tag_label,
        summary=pet_archive.sanitize_text(summary, max_chars=1000),
        selection=pet_archive.sanitize_text(selection, max_chars=4000),
        message=pet_archive.sanitize_text(message, max_chars=500),
        intent=intent,
        client_context=client_context,
        system_prompt=pet_archive.sanitize_text(system, max_chars=4000) or system,
        prior_turns=pet_archive.sanitize_turns(prior, max_chars=800),
        reply=reply,
        source=source,
        estimated_input_tokens=usage["estimated_input_tokens"],
        estimated_output_tokens=usage["estimated_output_tokens"],
        estimated_total_tokens=usage["estimated_total_tokens"],
        cache_hit=cache_hit,
        fallback_level=fallback_level,
    )
    u = PetUsageEvent(
        visitor_hash=visitor_hash,
        mode=mode,
        provider=source if source not in ("fallback", "rate_limited", "disabled", "cache") else None,
        source=source,
        estimated_input_tokens=usage["estimated_input_tokens"],
        estimated_output_tokens=usage["estimated_output_tokens"],
        estimated_total_tokens=usage["estimated_total_tokens"],
        cache_hit=cache_hit,
        fallback_level=fallback_level,
    )
    s.add_all([m, u])


@router.get("/pet/config", response_model=PublicPetConfig)
async def public_pet_config(
    request: Request,
    response: Response,
    s: AsyncSession = Depends(get_session),
) -> PublicPetConfig:
    cfg = await _load_pet_config(s)
    signed_vid, visitor_hash, is_new_vid = pet_identity.ensure_signed_vid(
        request.cookies.get(pet_identity.COOKIE_NAME)
    )
    if is_new_vid:
        _set_vid_cookie(response, signed_vid)
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
    try:
        await pet_profiles.touch(
            s,
            visitor_hash=visitor_hash,
            species=assigned,
            locale=request.headers.get("accept-language", "")[:32] or None,
        )
        await s.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("pet_config.profile_touch_failed", error=repr(e))
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
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    cfg = await _load_pet_config(s)
    ip_key = client_ip_key_part(request)
    signed_vid, visitor_hash, is_new_vid = pet_identity.ensure_signed_vid(
        request.cookies.get(pet_identity.COOKIE_NAME)
    )
    if is_new_vid:
        _set_vid_cookie(response, signed_vid)

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
        mode = req.mode or pet_prompt.infer_mode(
            post_id=post_id,
            selection=selection,
            message=req.message,
            client_context=req.client_context,
        )

    if _feature_disabled(cfg, mode):
        quip = random.choice(cfg.fallback_lines)
        await write_event(
            s, type="pet.summoned", actor=ip_hash(client_ip_from(request))[:12],
            meta={"source": "disabled", "mode": mode},
        )
        await s.commit()
        return {"quip": quip, "source": "disabled", "mode": mode}

    mode_breach = await pet_usage.check_mode_daily_limit(
        redis, visitor_hash=visitor_hash, mode=mode, limits=cfg.per_mode_daily_limit
    )
    if mode_breach is not None:
        quip = random.choice(cfg.tired_lines)
        await write_event(
            s, type="pet.summoned",
            actor=ip_hash(client_ip_from(request))[:12],
            meta={"source": "rate_limited", "breach": mode_breach, "mode": mode},
        )
        await s.commit()
        return {"quip": quip, "source": "rate_limited", "mode": mode}

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
        client_context=req.client_context,
        visitor_background=None,
    )
    messages = pet_prompt.build_messages(
        cfg, mode=mode, title=title, tag=tag_label, summary=summary,
        selection=selection, message=req.message, intent=req.intent,
        client_context=req.client_context, prior=[],
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
            user=messages[-1]["content"],
            fallback_lines=cfg.fallback_lines,
            max_tokens=pet_usage.output_budget_for(mode, cfg.per_mode_output_budget),
            temperature=pet_usage.temperature_for_mode(mode),
        )

    try:
        await pet_profiles.record_interaction(
            s, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
            tag=tag_label, message=req.message, locale=_client_locale(req),
        )
        usage = pet_usage.estimate_turn_tokens(system=system, messages=messages, reply=quip)
        await _record_usage_and_archive(
            s, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
            title=title, tag_label=tag_label, summary=summary, selection=selection,
            message=req.message, intent=req.intent, client_context=_clean_context(req),
            system=system, prior=[], reply=quip, source=source, usage=usage,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("pet_summon.archive_failed", error=repr(e))

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
    signed_vid, visitor_hash, is_new_vid = pet_identity.ensure_signed_vid(
        request.cookies.get(pet_identity.COOKIE_NAME)
    )

    # Resolve assigned species early so rate-limited archive carries real species
    # rather than "unknown".
    assigned = pet_assignment.verify_cookie(
        request.cookies.get(pet_assignment.COOKIE_NAME)
    ) or pet_assignment.assign_species(
        ip=client_ip_from(request),
        user_agent=request.headers.get("user-agent"),
    )

    if breach is not None:
        quip = random.choice(cfg.tired_lines)
        try:
            async with AsyncSessionLocal() as s2:
                m = PetMessage(
                    visitor_hash=visitor_hash, species=assigned,
                    mode="rate_limited",
                    system_prompt="(rate-limited; no LLM call)",
                    prior_turns=[],
                    reply=quip, source="rate_limited",
                    estimated_input_tokens=0,
                    estimated_output_tokens=0,
                    estimated_total_tokens=0,
                    fallback_level="L3",
                )
                u = PetUsageEvent(
                    visitor_hash=visitor_hash,
                    mode="rate_limited",
                    source="rate_limited",
                    estimated_input_tokens=0,
                    estimated_output_tokens=0,
                    estimated_total_tokens=0,
                    fallback_level="L3",
                )
                s2.add_all([m, u])
                await write_event(
                    s2, type="pet.summoned", actor=actor_hash,
                    meta={"source": "rate_limited", "breach": breach},
                )
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_rl", error=repr(e))

        async def rate_limited_stream():
            yield _sse({"type": "rate_limited", "text": quip, "breach": breach})

        resp = StreamingResponse(rate_limited_stream(), media_type="text/event-stream")
        if is_new_vid:
            _set_vid_cookie(resp, signed_vid)
        return resp

    # Mode + post lookup.
    if not cfg.enable_article_context:
        post_id = None
        selection = None
        mode: PetMode = "greet"
    else:
        post_id = req.post_id
        selection = req.selection
        mode = req.mode or pet_prompt.infer_mode(
            post_id=post_id,
            selection=selection,
            message=req.message,
            client_context=req.client_context,
        )

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

    if _feature_disabled(cfg, mode):
        quip = random.choice(cfg.fallback_lines)

        async def disabled_mode_stream():
            yield _sse({"type": "meta", "mode": mode, "species": assigned, "fallback_level": "L2"})
            yield _sse({"type": "fallback", "text": quip, "source": "disabled"})

        try:
            usage = {"estimated_input_tokens": 0, "estimated_output_tokens": 0, "estimated_total_tokens": 0}
            async with AsyncSessionLocal() as s2:
                await pet_profiles.record_interaction(
                    s2, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
                    tag=tag_label, message=req.message, locale=_client_locale(req),
                )
                await _record_usage_and_archive(
                    s2, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
                    title=title, tag_label=tag_label, summary=summary, selection=selection,
                    message=req.message, intent=req.intent, client_context=_clean_context(req),
                    system="(feature disabled; no LLM call)", prior=[], reply=quip,
                    source="disabled", usage=usage,
                )
                await write_event(
                    s2, type="pet.summoned", actor=actor_hash,
                    meta={"source": "disabled", "mode": mode, "species": assigned, "stream": True},
                )
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_disabled", error=repr(e))
        resp = StreamingResponse(disabled_mode_stream(), media_type="text/event-stream")
        if is_new_vid:
            _set_vid_cookie(resp, signed_vid)
        return resp

    mode_breach = await pet_usage.check_mode_daily_limit(
        redis, visitor_hash=visitor_hash, mode=mode, limits=cfg.per_mode_daily_limit
    )
    if mode_breach is not None:
        quip = random.choice(cfg.tired_lines)

        async def mode_limited_stream():
            yield _sse({"type": "rate_limited", "text": quip, "breach": mode_breach})

        try:
            async with AsyncSessionLocal() as s2:
                usage = {"estimated_input_tokens": 0, "estimated_output_tokens": 0, "estimated_total_tokens": 0}
                await _record_usage_and_archive(
                    s2, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
                    title=title, tag_label=tag_label, summary=summary, selection=selection,
                    message=req.message, intent=req.intent, client_context=_clean_context(req),
                    system="(mode-limited; no LLM call)", prior=[], reply=quip,
                    source="rate_limited", usage=usage,
                )
                await write_event(
                    s2, type="pet.summoned", actor=actor_hash,
                    meta={"source": "rate_limited", "breach": mode_breach, "mode": mode},
                )
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_mode_rl", error=repr(e))
        resp = StreamingResponse(mode_limited_stream(), media_type="text/event-stream")
        if is_new_vid:
            _set_vid_cookie(resp, signed_vid)
        return resp

    profile = None
    try:
        profile = await pet_profiles.touch(
            s, visitor_hash=visitor_hash, species=assigned, locale=_client_locale(req)
        )
        await s.commit()
    except Exception as e:  # noqa: BLE001
        log.warning("pet_summon_stream.profile_touch_failed", error=repr(e))

    system = pet_prompt.build_system(
        cfg, species=assigned, mode=mode,
        title=title, tag=tag_label, summary=summary, selection=selection,
        client_context=req.client_context,
        visitor_background=pet_profiles.background_summary(profile) if cfg.enable_long_term_memory else None,
    )

    prior: list[dict] = []
    try:
        prior = await pet_context.load(redis, visitor_hash, max_turns=cfg.context_window_turns)
    except Exception as e:  # noqa: BLE001
        log.warning("pet_summon_stream.ctx_load_failed", error=repr(e))

    messages = pet_prompt.build_messages(
        cfg, mode=mode,
        title=title, tag=tag_label, summary=summary, selection=selection,
        message=req.message, intent=req.intent, client_context=req.client_context,
        prior=prior,
    )
    archive_selection = pet_archive.sanitize_text(selection, max_chars=cfg.max_context_chars)
    archive_summary = pet_archive.sanitize_text(summary, max_chars=cfg.summary_max_chars)
    archive_system = pet_archive.sanitize_text(system, max_chars=4000) or system
    archive_prior = pet_archive.sanitize_turns(prior, max_chars=cfg.max_context_chars)

    # Capture for post-stream Redis append (last item is current user turn).
    current_user_turn = messages[-1].copy()
    cache_key = pet_cache.cache_key(
        mode=mode, post_id=post_id, selection=selection, message=req.message
    )
    if mode in ("summary_react", "selection_explain", "selection_qa", "code_assist", "article_finished"):
        try:
            cached_reply = await pet_cache.get(redis, cache_key)
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.cache_get_failed", error=repr(e))
            cached_reply = None
        if cached_reply:
            usage = pet_usage.estimate_turn_tokens(system=system, messages=messages, reply=cached_reply)
            try:
                async with AsyncSessionLocal() as s2:
                    await pet_profiles.record_interaction(
                        s2, visitor_hash=visitor_hash, species=assigned, mode=mode,
                        post_id=post_id, tag=tag_label, message=req.message, locale=_client_locale(req),
                    )
                    await _record_usage_and_archive(
                        s2, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
                        title=title, tag_label=tag_label, summary=summary, selection=selection,
                        message=req.message, intent=req.intent, client_context=_clean_context(req),
                        system=system, prior=archive_prior, reply=cached_reply, source="cache",
                        usage=usage, cache_hit=True,
                    )
                    await s2.commit()
            except Exception as e:  # noqa: BLE001
                log.warning("pet_summon_stream.archive_failed_cache", error=repr(e))

            async def cache_stream():
                yield _sse({"type": "meta", "mode": mode, "species": assigned, "fallback_level": "L1"})
                yield _sse({"type": "cache_hit"})
                yield _sse({"type": "chunk", "text": cached_reply})
                yield _sse({"type": "done", "source": "cache"})

            resp = StreamingResponse(cache_stream(), media_type="text/event-stream")
            if is_new_vid:
                _set_vid_cookie(resp, signed_vid)
            return resp

    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        await write_event(
            s, type="pet.summoned", actor=actor_hash,
            meta={"source": "fallback", "mode": mode, "species": assigned, "stream": True},
        )
        await s.commit()
        try:
            async with AsyncSessionLocal() as s2:
                await pet_profiles.record_interaction(
                    s2, visitor_hash=visitor_hash, species=assigned, mode=mode,
                    post_id=post_id, tag=tag_label, message=req.message, locale=_client_locale(req),
                )
                usage = pet_usage.estimate_turn_tokens(system=system, messages=messages, reply=quip)
                await _record_usage_and_archive(
                    s2, visitor_hash=visitor_hash, species=assigned, mode=mode, post_id=post_id,
                    title=title, tag_label=tag_label, summary=archive_summary,
                    selection=archive_selection, message=req.message, intent=req.intent,
                    client_context=_clean_context(req), system=archive_system, prior=archive_prior,
                    reply=quip, source="fallback", usage=usage,
                )
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_fallback", error=repr(e))

        async def disabled_stream():
            yield _sse({"type": "meta", "mode": mode, "species": assigned})
            yield _sse({"type": "fallback", "text": quip, "source": "fallback"})

        resp = StreamingResponse(disabled_stream(), media_type="text/event-stream")
        if is_new_vid:
            _set_vid_cookie(resp, signed_vid)
        return resp

    secrets = await _resolve_secrets(s, cfg.providers)
    # Capture immutables for the generator; dropping `s` so we don't depend
    # on session lifetime during chunked send.
    providers = list(cfg.providers)
    fallback_lines = list(cfg.fallback_lines)

    async def event_stream():
        terminal_source = "fallback"
        accumulated_chunks: list[str] = []
        fallback_text: str | None = None
        try:
            yield _sse({"type": "meta", "mode": mode, "species": assigned})
            async for evt in pet_gateway.summon_stream(
                providers=providers,
                secrets=secrets,
                system=system,
                messages=messages,
                fallback_lines=fallback_lines,
                max_tokens=pet_usage.output_budget_for(mode, cfg.per_mode_output_budget),
                temperature=pet_usage.temperature_for_mode(mode),
            ):
                if evt.get("type") == "chunk":
                    accumulated_chunks.append(evt.get("text", ""))
                elif evt.get("type") == "fallback":
                    fallback_text = (evt.get("text") or "").strip()
                yield _sse(evt)
                if evt.get("type") in ("done", "fallback"):
                    terminal_source = evt.get("source", "fallback")
                    break
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.error", error=repr(e))
            yield _sse({"type": "error", "message": "stream failed"})

        full_reply = "".join(accumulated_chunks).strip()

        async def _flush():
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
                try:
                    if pet_cache.cacheable(
                        source=terminal_source, reply=full_reply,
                        selection=selection, message=req.message,
                    ):
                        await pet_cache.set(redis, cache_key, full_reply)
                except Exception as e:  # noqa: BLE001
                    log.warning("pet_summon_stream.cache_set_failed", error=repr(e))

            # Archive every turn (including fallback) to pet_message.
            if full_reply or terminal_source == "fallback":
                archive_reply = full_reply or fallback_text or random.choice(fallback_lines)
                try:
                    async with AsyncSessionLocal() as s2:
                        await pet_profiles.record_interaction(
                            s2, visitor_hash=visitor_hash, species=assigned, mode=mode,
                            post_id=post_id, tag=tag_label, message=req.message,
                            locale=_client_locale(req),
                        )
                        usage = pet_usage.estimate_turn_tokens(
                            system=system, messages=messages, reply=archive_reply
                        )
                        await _record_usage_and_archive(
                            s2, visitor_hash=visitor_hash, species=assigned, mode=mode,
                            post_id=post_id, title=title, tag_label=tag_label,
                            summary=archive_summary, selection=archive_selection,
                            message=req.message, intent=req.intent,
                            client_context=_clean_context(req), system=archive_system,
                            prior=archive_prior, reply=archive_reply, source=terminal_source,
                            usage=usage,
                        )
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

        try:
            await asyncio.shield(_flush())
        except asyncio.CancelledError:
            # Already shielded — only propagates if shield itself cancelled twice.
            pass

    resp = StreamingResponse(event_stream(), media_type="text/event-stream")
    if is_new_vid:
        _set_vid_cookie(resp, signed_vid)
    return resp


@router.post("/pet/forget")
async def public_pet_forget(
    request: Request,
    response: Response,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> dict:
    signed = request.cookies.get(pet_identity.COOKIE_NAME)
    visitor_hash = pet_identity.visitor_hash_from_parts(
        signed_vid=signed,
        ip=client_ip_from(request),
    )
    await s.execute(delete(PetVisitorProfile).where(PetVisitorProfile.visitor_hash == visitor_hash))
    await s.commit()
    try:
        await pet_context.clear(redis, visitor_hash)
    except Exception as e:  # noqa: BLE001
        log.warning("pet_forget.ctx_clear_failed", error=repr(e))
    response.delete_cookie(pet_identity.COOKIE_NAME, path="/")
    return {"forgotten": True}
