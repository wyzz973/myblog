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


def _safe_format(template: str, /, **vars: str) -> str:
    """`str.format`-like substitution that ignores unknown `{name}`s.

    Also avoids interpreting braces inside substituted values: we use
    Formatter.vformat with a SafeDict so the substitution pass replaces
    only the explicit placeholders we provide.
    """
    return string.Formatter().vformat(template, (), _SafeDict(**vars))


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
        summary=(summary or "")[:200],
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
