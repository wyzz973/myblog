"""ARQ analytics_rollup: hit_events → hit_daily, then prune raw > 30 days."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent
from app.services.event_log import write_event


def _parse_date(s: str | None) -> date:
    if s is None:
        return (datetime.now(UTC) - timedelta(days=1)).date()
    return date.fromisoformat(s)


async def analytics_rollup(ctx: dict, target_date: str | None = None) -> dict:
    """Roll one UTC day of hit_events into hit_daily, then truncate raw > 30 days.

    Idempotent: re-running for the same target_date overwrites the
    (date, path) rows in hit_daily.
    """
    d = _parse_date(target_date)
    start = datetime.combine(d, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

    paths_rolled = 0
    try:
        async with AsyncSessionLocal() as s:
            # Group by path: count + a representative post_id (MIN if any).
            grouped = await s.execute(
                select(
                    HitEvent.path,
                    HitEvent.post_id,
                    HitEvent.referrer,
                    HitEvent.country,
                ).where(HitEvent.created_at >= start).where(HitEvent.created_at < end)
            )
            buckets: dict[str, dict] = {}
            for path, post_id, referrer, country in grouped.all():
                b = buckets.setdefault(path, {
                    "path": path,
                    "post_id": post_id,
                    "refs": Counter(),
                    "countries": Counter(),
                    "hits": 0,
                })
                b["hits"] += 1
                # Pick first non-NULL post_id seen.
                if b["post_id"] is None and post_id is not None:
                    b["post_id"] = post_id
                if referrer:
                    b["refs"][referrer] += 1
                if country:
                    b["countries"][country] += 1

            for path, b in buckets.items():
                top_refs = [
                    {"r": r, "n": n} for r, n in b["refs"].most_common(10)
                ]
                top_countries = [
                    {"c": c, "n": n} for c, n in b["countries"].most_common(10)
                ]
                stmt = pg_insert(HitDaily).values(
                    date=d, path=path, hits=b["hits"], post_id=b["post_id"],
                    referrers_top=top_refs, countries_top=top_countries,
                ).on_conflict_do_update(
                    index_elements=["date", "path"],
                    set_={
                        "hits": b["hits"],
                        "post_id": b["post_id"],
                        "referrers_top": top_refs,
                        "countries_top": top_countries,
                    },
                )
                await s.execute(stmt)
                paths_rolled += 1

            cutoff = datetime.now(UTC) - timedelta(days=30)
            res = await s.execute(delete(HitEvent).where(HitEvent.created_at < cutoff))
            rows_truncated = res.rowcount or 0

            await write_event(
                s, type="analytics.rollup", actor="system",
                target=d.isoformat(),
                meta={
                    "date": d.isoformat(),
                    "paths_rolled": paths_rolled,
                    "rows_truncated": rows_truncated,
                },
            )
            await s.commit()
    except Exception as e:
        async with AsyncSessionLocal() as s2:
            await write_event(
                s2, type="analytics.rollup_failed", actor="system",
                target=d.isoformat(),
                meta={"date": d.isoformat(), "error": str(e)},
            )
            await s2.commit()
        raise

    return {
        "date": d.isoformat(),
        "paths_rolled": paths_rolled,
        "rows_truncated": rows_truncated,
    }
