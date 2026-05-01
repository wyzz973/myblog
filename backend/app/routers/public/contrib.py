from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ContribDay

router = APIRouter()

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _months_for_window(today: date, weeks: int) -> list[str]:
    """Walk the displayed weeks and emit one month label per distinct month."""
    seen = []
    for w in range(weeks):
        # date of the Sunday at the start of week w (display order: oldest → newest)
        anchor = today - timedelta(days=(weeks - 1 - w) * 7 + 6)
        m = _MONTH_NAMES[anchor.month - 1]
        if not seen or seen[-1] != m:
            seen.append(m)
    return seen


@router.get("/contrib")
async def get_contrib(
    weeks: int = Query(52, ge=1, le=104),
    s: AsyncSession = Depends(get_session),
) -> dict:
    rows = (await s.execute(select(ContribDay))).scalars().all()
    by_day = {r.day: r for r in rows}
    today = date.today()
    grid: list[list[int]] = [[0] * 7 for _ in range(weeks)]
    counts: list[list[int]] = [[0] * 7 for _ in range(weeks)]
    commits = 0
    start_day: date | None = None
    end_day: date | None = None
    for w in range(weeks):
        for d in range(7):
            day = today - timedelta(days=(weeks - 1 - w) * 7 + (6 - d))
            if start_day is None or day < start_day:
                start_day = day
            if end_day is None or day > end_day:
                end_day = day
            r = by_day.get(day)
            if r is not None:
                grid[w][d] = r.level
                counts[w][d] = r.count
                commits += r.count
    return {
        "weeks": weeks,
        "grid": grid,
        "counts": counts,
        "months": _months_for_window(today, weeks),
        "commits": commits,
        "start": start_day.isoformat() if start_day else None,
        "end": end_day.isoformat() if end_day else None,
        "source": "github" if rows else "empty",
    }
