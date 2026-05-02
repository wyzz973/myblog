"""Prompt assembly for the pet personality system.

The final system prompt is three layers:

    BASE_INSTRUCTION.format(species, persona)
    + "\n\n"
    + mode_template.format(title, tag, summary, selection)

Unknown placeholders inside the mode template are left literal so a
typo in the admin UI doesn't break inference. Selection text is
truncated to PetConfig.max_context_chars before substitution.
"""
from __future__ import annotations

import string

from app.schemas.pet import PetConfig, PetMode
from app.services.pet_defaults import BASE_INSTRUCTION


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


def build_system(
    cfg: PetConfig,
    *,
    species: str,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    selection: str | None,
) -> str:
    """Assemble the final system prompt for one /pet/summon request."""
    persona = getattr(cfg.personas, species, None)
    if not persona:
        # Unknown species (catalog drift) — fall back to legacy single prompt.
        return cfg.system_prompt

    base = BASE_INSTRUCTION.format(species=species, persona=persona)
    template = getattr(cfg.mode_templates, mode)
    body = _safe_format(
        template,
        title=title or "",
        tag=tag or "",
        summary=(summary or "")[:cfg.summary_max_chars],
        selection=truncate_selection(selection, cfg.max_context_chars),
    )
    return f"{base}\n\n{body}"


def infer_mode(*, post_id: str | None, selection: str | None) -> PetMode:
    """Server-side default when frontend didn't pass an explicit mode.

    Note: this never returns 'selection_explain' — the code-vs-prose
    discrimination must be done by the frontend (it owns the DOM).
    """
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
    prior: list[dict],
) -> list[dict]:
    """Compose the messages array for the LLM gateway.

    Returns: prior turns (user/assistant alternating, role+content only)
    followed by a single new user turn whose content is a "scene tag"
    describing what the visitor just did. The system prompt is built
    separately by build_system().
    """
    selection_text = truncate_selection(selection, cfg.max_context_chars) if selection else ""
    title_text = title or ""
    tag_text = tag or ""

    if mode == "greet":
        scene = "(visitor tapped on you)"
    elif mode == "idle_monologue":
        scene = "(visitor has been idle; say a spontaneous thought)"
    elif mode == "summary_react":
        scene = f'(visitor reading "{title_text}", tag: {tag_text})'
    elif mode == "selection_explain":
        scene = f'(visitor highlighted code from "{title_text}"): {selection_text}'
    elif mode == "selection_qa":
        scene = f'(visitor highlighted from "{title_text}"): {selection_text}'
    else:
        scene = "(visitor summoned you)"

    cleaned_prior = [
        {"role": t.get("role", "user"), "content": t.get("content", "")}
        for t in prior
        if t.get("role") in ("user", "assistant")
    ]
    return [*cleaned_prior, {"role": "user", "content": scene}]
