"""LLM cost rates for the pet usage cost chart (Task 36).

Rates are USD per 1,000,000 tokens. Each provider stores its own override
inside its existing Integration.extra_json under `cost_in_per_m` /
`cost_out_per_m`. Providers without a row return the hardcoded default
below. The cost chart on /admin/pet?tab=usage reads these via
`GET /api/admin/pet/cost-rates`.

Why not a dedicated table: rates are per-provider already because each
LLM has its own Integration row. Co-locating keeps the surface tiny —
no migration, no extra model, no separate CRUD.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Integration

# Aligned with PROVIDER_RATES in src/admin/pet/petUsageChart.js. The
# "default" entry is what's used when the user picks an unknown provider
# slug or when an Integration row hasn't been created yet.
DEFAULT_RATES: dict[str, dict[str, float]] = {
    "anthropic": {"in_per_m": 3.00, "out_per_m": 15.00},
    "zhipu":     {"in_per_m": 0.08, "out_per_m": 0.16},
    "qwen":      {"in_per_m": 0.10, "out_per_m": 0.30},
    "doubao":    {"in_per_m": 0.05, "out_per_m": 0.15},
    "deepseek":  {"in_per_m": 0.27, "out_per_m": 1.10},
    "default":   {"in_per_m": 0.50, "out_per_m": 1.50},
}

LLM_PROVIDERS = ("anthropic", "zhipu", "qwen", "doubao", "deepseek")


def _override(extra: dict[str, Any] | None) -> dict[str, float] | None:
    if not extra:
        return None
    raw_in = extra.get("cost_in_per_m")
    raw_out = extra.get("cost_out_per_m")
    if raw_in is None and raw_out is None:
        return None
    return {
        "in_per_m": float(raw_in) if raw_in is not None else 0.0,
        "out_per_m": float(raw_out) if raw_out is not None else 0.0,
    }


async def get_all(s: AsyncSession) -> dict[str, dict[str, float]]:
    """Returns a {provider: {in_per_m, out_per_m}} map.

    Each LLM provider entry is the override-or-default rate. The "default"
    key is included so callers can compute cost for unknown sources.
    """
    rows = (
        await s.execute(select(Integration).where(Integration.name.in_(LLM_PROVIDERS)))
    ).scalars().all()
    by_name = {r.name: r for r in rows}
    out: dict[str, dict[str, float]] = {}
    for name in LLM_PROVIDERS:
        row = by_name.get(name)
        override = _override(row.extra_json if row else None)
        out[name] = override or DEFAULT_RATES.get(name, DEFAULT_RATES["default"]).copy()
    out["default"] = DEFAULT_RATES["default"].copy()
    return out


async def set_rate(
    s: AsyncSession,
    *,
    provider: str,
    in_per_m: float,
    out_per_m: float,
) -> None:
    """Persist override for one provider into its Integration.extra_json.

    No-op for providers without an existing Integration row — owner must
    configure the API key first via /integrations/<provider>. We emit
    nothing in that case; the caller can surface a 404.
    """
    if provider not in LLM_PROVIDERS:
        raise ValueError(f"unknown provider: {provider!r}")
    if in_per_m < 0 or out_per_m < 0:
        raise ValueError("rates must be non-negative")
    row = (
        await s.execute(select(Integration).where(Integration.name == provider))
    ).scalar_one_or_none()
    if row is None:
        raise LookupError(f"integration {provider!r} not configured")
    extras = dict(row.extra_json or {})
    extras["cost_in_per_m"] = float(in_per_m)
    extras["cost_out_per_m"] = float(out_per_m)
    row.extra_json = extras
    await s.flush()
