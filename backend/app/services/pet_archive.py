"""Helpers for storing pet conversation archives safely."""
from __future__ import annotations

import re
from typing import Any

SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|secret|token|password)"
        r"(\s*[:=]\s*)"
        r"([A-Za-z0-9._~+/=-]{8,})"
    ),
]


def sanitize_text(text: str | None, *, max_chars: int) -> str | None:
    """Redact common secret shapes and cap stored archive text."""
    if text is None:
        return None
    out = text
    out = SECRET_PATTERNS[0].sub("[redacted]", out)
    out = SECRET_PATTERNS[1].sub(r"\1\2[redacted]", out)
    return out[:max_chars]


def sanitize_turns(turns: list[dict[str, Any]], *, max_chars: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for turn in turns:
        role = turn.get("role")
        if role not in ("user", "assistant"):
            continue
        content = sanitize_text(str(turn.get("content", "")), max_chars=max_chars) or ""
        out.append({"role": role, "content": content})
    return out
