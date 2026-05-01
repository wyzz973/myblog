from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ContribDay

router = APIRouter()

_MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _last_saturday(today: date) -> date:
    """Saturday of the week that contains ``today`` (Sun=start of week).

    Python's weekday(): Mon=0..Sun=6. Convert to Sun=0..Sat=6 so we can
    reach Saturday by adding ``6 - dow`` days.
    """
    dow_sun_first = (today.weekday() + 1) % 7  # Sun=0..Sat=6
    return today + timedelta(days=6 - dow_sun_first)


def _months_for_window(today: date, weeks: int) -> list[str]:
    """One month label per distinct month visible in the calendar.

    Each column spans Sun→Sat. A label is attributed to a column when it
    contains the *first day* of a month. The very first column always
    gets a label (start of window). This matches GitHub's behavior:
    when today's week straddles months (e.g. 4/26 → 5/2 with today=5/1),
    the rightmost column is labeled with the new month, not the old one.
    """
    last_sat = _last_saturday(today)
    seen: list[str] = []
    for w in range(weeks):
        col_sun = last_sat - timedelta(days=(weeks - 1 - w) * 7 + 6)
        # Find a month-start day inside the column's 7 days.
        label: str | None = None
        for d in range(7):
            day = col_sun + timedelta(days=d)
            if day.day == 1:
                label = _MONTH_NAMES[day.month - 1]
                break
        # Always show the leftmost label (start of window).
        if label is None and w == 0:
            label = _MONTH_NAMES[col_sun.month - 1]
        if label is not None and (not seen or seen[-1] != label):
            seen.append(label)
    return seen


@router.get("/contrib")
async def get_contrib(
    weeks: int = Query(52, ge=1, le=104),
    s: AsyncSession = Depends(get_session),
) -> dict:
    rows = (await s.execute(select(ContribDay))).scalars().all()
    by_day = {r.day: r for r in rows}
    today = date.today()
    last_sat = _last_saturday(today)
    grid: list[list[int]] = [[0] * 7 for _ in range(weeks)]
    counts: list[list[int]] = [[0] * 7 for _ in range(weeks)]
    commits = 0
    start_day: date | None = None
    end_day: date | None = None
    for w in range(weeks):
        col_sun = last_sat - timedelta(days=(weeks - 1 - w) * 7 + 6)
        for d in range(7):
            day = col_sun + timedelta(days=d)  # d=0 Sun .. d=6 Sat
            if day > today:
                # future cell inside the current week — leave blank
                continue
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
