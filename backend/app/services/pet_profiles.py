"""Low-sensitivity anonymous visitor profile updates for pet memory."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PetVisitorProfile


def infer_language(*, message: str | None = None, locale: str | None = None) -> str | None:
    text = message or ""
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return "zh"
    if locale:
        low = locale.lower()
        if low.startswith("zh"):
            return "zh"
        if low.startswith("en"):
            return "en"
    if text:
        return "en"
    return None


def _append_unique(values: list[str] | None, item: str | None, *, cap: int) -> list[str]:
    out = [str(v) for v in (values or []) if v]
    if item:
        item = str(item)
        out = [v for v in out if v != item]
        out.insert(0, item)
    return out[:cap]


def _style_from_message(message: str | None, existing: str | None) -> str | None:
    if not message:
        return existing
    hints: list[str] = []
    if any(word in message.lower() for word in ("code", "cleanup", "bug", "hook", "api", "函数", "代码")):
        hints.append("喜欢代码解释")
    if any(word in message for word in ("总结", "核心", "重点", "summary")):
        hints.append("喜欢短总结")
    if any(word in message for word in ("继续", "为什么", "举个例子", "why", "example")):
        hints.append("会连续追问")
    if not hints:
        return existing
    merged = []
    for part in [*(existing or "").split("；"), *hints]:
        part = part.strip()
        if part and part not in merged:
            merged.append(part)
    return "；".join(merged[:5])[:500]


async def touch(
    s: AsyncSession,
    *,
    visitor_hash: str,
    species: str,
    locale: str | None = None,
    now: datetime | None = None,
) -> PetVisitorProfile:
    now = now or datetime.now(UTC)
    row = await s.get(PetVisitorProfile, visitor_hash)
    if row is None:
        row = PetVisitorProfile(
            visitor_hash=visitor_hash,
            species=species,
            locale=locale,
            preferred_language=infer_language(locale=locale),
            last_seen_at=now,
        )
        s.add(row)
    else:
        row.species = species
        row.locale = locale or row.locale
        row.last_seen_at = now
        if locale and not row.preferred_language:
            row.preferred_language = infer_language(locale=locale)
    return row


async def record_interaction(
    s: AsyncSession,
    *,
    visitor_hash: str,
    species: str,
    mode: str,
    post_id: str | None,
    tag: str | None,
    message: str | None,
    locale: str | None,
    now: datetime | None = None,
) -> PetVisitorProfile:
    now = now or datetime.now(UTC)
    row = await touch(s, visitor_hash=visitor_hash, species=species, locale=locale, now=now)
    row.interaction_count = (row.interaction_count or 0) + 1
    row.last_interaction_at = now
    lang = infer_language(message=message, locale=locale)
    if lang:
        row.preferred_language = lang
    row.interest_tags = _append_unique(row.interest_tags, tag, cap=12)
    row.recent_post_ids = _append_unique(row.recent_post_ids, post_id, cap=10)
    row.style_summary = _style_from_message(message, row.style_summary)
    row.extra_json = {**(row.extra_json or {}), "last_mode": mode}
    return row


def background_summary(profile: PetVisitorProfile | None) -> str | None:
    if profile is None:
        return None
    parts: list[str] = []
    if profile.preferred_language:
        parts.append(f"preferred_language: {profile.preferred_language}")
    if profile.interest_tags:
        parts.append(f"recent_interest_tags: {', '.join(profile.interest_tags[:6])}")
    if profile.recent_post_ids:
        parts.append(f"recent_posts: {', '.join(profile.recent_post_ids[:5])}")
    if profile.style_summary:
        parts.append(f"interaction_style: {profile.style_summary}")
    if profile.memory_summary:
        parts.append(f"memory_summary: {profile.memory_summary[:260]}")
    if profile.interaction_count:
        parts.append(f"interaction_count: {profile.interaction_count}")
    return "\n".join(parts)[:500] if parts else None
