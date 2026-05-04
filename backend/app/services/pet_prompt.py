"""Prompt assembly for the pet personality system.

The final system prompt is three layers:

    BASE_INSTRUCTION.format(species, persona, behavior, visitor_background)
    + "\n\n"
    + mode_template.format(title, tag, summary, selection)

Unknown placeholders inside the mode template are left literal so a
typo in the admin UI doesn't break inference. Selection text is
truncated to PetConfig.max_context_chars before substitution.
"""
from __future__ import annotations

import json
import string
from typing import Any

from app.schemas.pet import PetConfig, PetMode
from app.services import pet_archive
from app.services.pet_defaults import BASE_INSTRUCTION, DEFAULT_BEHAVIOR


class _SafeDict(dict):
    """dict that returns '{key}' for missing keys instead of KeyError."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class _SafeFormatter(string.Formatter):
    """Formatter that:
    - returns "{key}" literal for unknown keys (via _SafeDict)
    - disallows attribute/index traversal: {title.foo} or {title[0]} are
      treated as the field name "title.foo" / "title[0]" — looked up in
      the SafeDict, not found, returned literal as-is.
    - ignores format specs entirely: {title:>1000000000} becomes the
      stringified value, not a billion-character pad. Without this, an
      admin-typed template could OOM the worker.
    - never raises on malformed templates (returns the template unchanged
      if vformat fails for any reason).
    """

    def get_field(self, field_name, args, kwargs):
        # Disable attribute/index access by treating the entire name as a key.
        return self.get_value(field_name, args, kwargs), field_name

    def format_field(self, value, format_spec):
        # Ignore format specs (alignment / width / precision / type).
        # Defends against memory amplification from admin-typed templates
        # like {title:>1000000000}.
        return str(value)


def _safe_format(template: str, /, **values: str) -> str:
    """str.format-style substitution that ignores unknown {name}s and never
    raises on admin-typed garbage templates.

    Substituted values are not re-interpreted (literal { and } in values
    are passed through unchanged). Attribute and index traversal in
    placeholders is disabled — {title.foo} stays literal.
    """
    try:
        return _SafeFormatter().vformat(template, (), _SafeDict(**values))
    except (IndexError, ValueError, KeyError):
        return template


def truncate_selection(selection: str | None, max_chars: int) -> str:
    if not selection:
        return ""
    return selection[:max_chars]


FOLLOW_UP_MESSAGES = {
    "继续", "接着说", "为什么", "为啥", "然后呢", "举个例子", "那怎么办",
    "continue", "why", "more", "example", "go on",
}

SUMMARY_REACTION_ANGLES = (
    "risk_or_caveat",
    "curious_follow_up",
    "specific_joke",
    "practical_next_step",
    "tiny_hot_take",
)

CONTENT_AWARE_MODES = {
    "summary_react",
    "selection_explain",
    "selection_qa",
    "free_chat",
    "follow_up",
    "article_finished",
    "reading_assist",
    "code_assist",
    "recommend_next",
}


def _behavior_text(species: str) -> str:
    behavior = DEFAULT_BEHAVIOR.get(species, DEFAULT_BEHAVIOR.get("cat", {}))
    return "\n".join(f"{k}: {v}" for k, v in behavior.items())


def _context_dict(client_context: Any) -> dict[str, Any]:
    if client_context is None:
        return {}
    if hasattr(client_context, "model_dump"):
        data = client_context.model_dump(exclude_none=True)
    elif isinstance(client_context, dict):
        data = {k: v for k, v in client_context.items() if v is not None}
    else:
        return {}
    allow = {
        "page_type", "path", "title", "tag", "read_progress", "active_heading",
        "visible_block_type", "selection_kind", "dwell_seconds", "recent_action",
        "locale", "timezone", "active_tag", "post_count", "focused_post_title",
        "focused_post_tag", "focused_post_subtitle", "home_digest", "visible_posts",
    }
    string_caps = {
        "home_digest": 600,
        "focused_post_title": 160,
        "focused_post_subtitle": 160,
    }
    out: dict[str, Any] = {}
    for key in allow:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            out[key] = value[:string_caps.get(key, 180)]
        elif isinstance(value, list):
            out[key] = [str(item).strip()[:120] for item in value[:8] if str(item).strip()]
        elif isinstance(value, (int, float, bool)):
            out[key] = value
    return out


def serialize_context(client_context: Any, *, max_chars: int = 1200) -> dict[str, Any]:
    data = _context_dict(client_context)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if len(raw) <= max_chars:
        return data
    # Drop least important verbose fields first.
    for key in ("path", "title", "active_heading", "timezone", "home_digest", "visible_posts"):
        data.pop(key, None)
        raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
        if len(raw) <= max_chars:
            return data
    return {}


def _scene_lines(
    *,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    client_context: Any,
) -> list[str]:
    lines = ["[SCENE]"]
    ctx = serialize_context(client_context)
    if title:
        lines.append(f"post_title: {title[:160]}")
    if tag:
        lines.append(f"tag: {tag[:40]}")
    if summary:
        lines.append(f"summary: {(summary or '')[:260]}")
    for key, value in ctx.items():
        lines.append(f"{key}: {value}")
    lines.append("")
    lines.append("[TASK]")
    lines.append(f"mode: {mode}")
    lines.append(f"description: {_mode_scene_fallback(mode, title, tag)}")
    return lines


def _mode_scene_fallback(mode: PetMode, title: str | None, tag: str | None) -> str:
    title_text = title or ""
    tag_text = tag or ""
    if mode == "greet":
        return "(visitor tapped on you)"
    if mode == "idle_monologue":
        return "(visitor has been idle; say a spontaneous thought)"
    if mode == "summary_react":
        return f'(visitor reading "{title_text}", tag: {tag_text})'
    if mode == "selection_explain":
        return f'(visitor highlighted code from "{title_text}")'
    if mode == "selection_qa":
        return f'(visitor highlighted from "{title_text}")'
    if mode == "article_finished":
        return f'(visitor finished reading "{title_text}")'
    if mode == "code_assist":
        return f'(visitor wants help with code in "{title_text}")'
    if mode == "recommend_next":
        return f'(visitor wants a page-aware next read after tag {tag_text})'
    return "(visitor summoned you)"


def _recent_assistant_replies(prior: list[dict], *, max_items: int = 3) -> list[str]:
    replies = [
        str(t.get("content", "")).strip()
        for t in prior
        if t.get("role") == "assistant" and str(t.get("content", "")).strip()
    ]
    return replies[-max_items:]


def build_system(
    cfg: PetConfig,
    *,
    species: str,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    selection: str | None,
    client_context: Any = None,
    visitor_background: str | None = None,
) -> str:
    """Assemble the final system prompt for one /pet/summon request."""
    persona = getattr(cfg.personas, species, None)
    if not persona:
        # Unknown species (catalog drift) — fall back to legacy single prompt.
        return cfg.system_prompt

    base = BASE_INSTRUCTION.format(
        species=species,
        persona=persona,
        behavior=_behavior_text(species),
        visitor_background=(visitor_background or "No durable anonymous background yet.")[:500],
    )
    template = getattr(cfg.mode_templates, mode)
    body = _safe_format(
        template,
        title=title or "",
        tag=tag or "",
        summary=(summary or "")[:cfg.summary_max_chars],
        selection=truncate_selection(selection, cfg.max_context_chars),
    )
    return f"{base}\n\n{body}"


def infer_mode(*, post_id: str | None, selection: str | None, message: str | None = None,
               client_context: Any = None) -> PetMode:
    """Server-side default when frontend didn't pass an explicit mode.

    Note: this never returns 'selection_explain' — the code-vs-prose
    discrimination must be done by the frontend (it owns the DOM).
    """
    if message:
        msg = message.strip().lower()
        if msg in FOLLOW_UP_MESSAGES or len(msg) <= 6 and msg.rstrip("?？") in FOLLOW_UP_MESSAGES:
            return "follow_up"
        return "free_chat"
    ctx = _context_dict(client_context)
    if ctx.get("recent_action") == "reached_end":
        return "article_finished"
    if ctx.get("visible_block_type") == "code" or ctx.get("selection_kind") == "code":
        return "code_assist" if selection else "summary_react"
    if selection:
        return "selection_qa"
    if post_id:
        return "summary_react"
    return "greet"


def build_messages(
    cfg: PetConfig,
    *,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    selection: str | None,
    message: str | None,
    intent: str | None,
    client_context: Any,
    prior: list[dict],
) -> list[dict]:
    """Compose the messages array for the LLM gateway.

    Returns: prior turns (user/assistant alternating, role+content only)
    followed by a single new user turn whose content is a "scene tag"
    describing what the visitor just did. The system prompt is built
    separately by build_system().
    """
    selection_text = truncate_selection(selection, cfg.max_context_chars) if selection else ""
    sanitized_selection = pet_archive.sanitize_text(selection_text, max_chars=cfg.max_context_chars) or ""
    sanitized_message = pet_archive.sanitize_text(message, max_chars=500) if message else None

    scene_lines = _scene_lines(
        mode=mode, title=title, tag=tag, summary=summary, client_context=client_context
    )
    if intent:
        scene_lines.append(f"intent: {intent[:48]}")
    if mode in CONTENT_AWARE_MODES:
        scene_lines.append(
            "natural_speech_constraint: zero stock catchphrases; zero unrelated hunger/tiredness/snack/sleep/body-state jokes; avoid formulaic parenthetical openings"
        )
    if mode in ("summary_react", "recommend_next"):
        replies = _recent_assistant_replies(prior)
        angle = SUMMARY_REACTION_ANGLES[len(replies) % len(SUMMARY_REACTION_ANGLES)]
        scene_lines.append(f"reaction_angle: {angle}")
        if replies:
            scene_lines.append("avoid_repeating_recent_assistant_replies:")
            for reply in replies:
                scene_lines.append(f"- {reply[:120]}")
    if sanitized_message:
        scene_lines.extend(["", "[VISITOR_MESSAGE]", sanitized_message])
    elif not scene_lines:
        scene_lines.append(_mode_scene_fallback(mode, title, tag))
    if sanitized_selection:
        scene_lines.extend(["", "[UNTRUSTED_SELECTION]", sanitized_selection, "[/UNTRUSTED_SELECTION]"])
    scene = "\n".join(scene_lines).strip()

    if (
        mode not in ("summary_react",)
        and not sanitized_message
        and not sanitized_selection
        and not serialize_context(client_context)
    ):
        scene = _mode_scene_fallback(mode, title, tag)

    cleaned_prior = [
        {"role": t.get("role", "user"), "content": t.get("content", "")}
        for t in prior
        if t.get("role") in ("user", "assistant")
    ]
    return [*cleaned_prior, {"role": "user", "content": scene}]
