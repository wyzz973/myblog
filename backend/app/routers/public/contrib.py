from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ContribDay

router = APIRouter()

_MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]


def _seed_grid() -> list[list[int]]:
    """Deterministic LCG fallback that mirrors the original frontend data.js generator."""
    s = 42
    grid: list[list[int]] = []
    for _w in range(52):
        col: list[int] = []
        for d in range(7):
            s = (s * 9301 + 49297) % 233280
            r = s / 233280
            weekday = 1.2 if 0 < d < 6 else 0.6
            v = r * weekday
            level = 0
            if v > 0.35:
                level = 1
            if v > 0.6:
                level = 2
            if v > 0.8:
                level = 3
            if v > 0.93:
                level = 4
            col.append(level)
        grid.append(col)
    return grid


@router.get("/contrib")
async def get_contrib(
    weeks: int = Query(52, ge=1, le=104),
    s: AsyncSession = Depends(get_session),
) -> dict:
    rows = (await s.execute(select(ContribDay))).scalars().all()
    if not rows:
        grid = _seed_grid()
        commits = 1384
        return {
            "weeks": weeks, "grid": grid, "months": _MONTHS,
            "commits": commits, "source": "seed",
        }

    by_day = {r.day: r for r in rows}
    today = date.today()
    grid: list[list[int]] = [[0] * 7 for _ in range(weeks)]
    commits = 0
    for w in range(weeks):
        for d in range(7):
            day = today - timedelta(days=(weeks - 1 - w) * 7 + (6 - d))
            r = by_day.get(day)
            if r is not None:
                grid[w][d] = r.level
                commits += r.count
    return {
        "weeks": weeks, "grid": grid, "months": _MONTHS,
        "commits": commits, "source": "github",
    }
