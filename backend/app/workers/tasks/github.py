"""ARQ task: sync_github_contrib + sync_github_repos."""
from __future__ import annotations

import structlog
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.models import ContribDay, Project
from app.services import github as github_svc
from app.services import integrations as integrations_svc
from app.services.event_log import write_event

log = structlog.get_logger(__name__)


async def sync_github_contrib(ctx: dict) -> dict:
    """Pull latest 52-week contribution calendar; upsert contrib_days."""
    async with AsyncSessionLocal() as s:
        row = await integrations_svc.get(s, name="github")
        if row is None or row.username is None:
            return {"count": 0, "skipped": "no integration configured"}
        token = await integrations_svc.get_secret(s, name="github")
        if token is None:
            return {"count": 0, "skipped": "no token"}
        username = row.username

    try:
        days = await github_svc.fetch_contributions(token, username)
    except Exception as e:  # noqa: BLE001
        log.warning("github.fetch_failed", username=username, error=str(e))
        async with AsyncSessionLocal() as s:
            await integrations_svc.set_status(s, name="github", status="failed", error=str(e)[:512])
            await write_event(
                s, type="integration.github.failed", actor="worker",
                meta={"username": username, "error": str(e)[:512]},
            )
            await s.commit()
        raise

    async with AsyncSessionLocal() as s:
        for d in days:
            stmt = pg_insert(ContribDay).values(
                day=d["day"], count=d["count"], level=d["level"],
            ).on_conflict_do_update(
                index_elements=[ContribDay.day],
                set_={"count": d["count"], "level": d["level"]},
            )
            await s.execute(stmt)
        await integrations_svc.set_status(s, name="github", status="ok", error=None)
        days_with_activity = sum(1 for d in days if d["count"] > 0)
        await write_event(
            s, type="integration.github.synced", actor="worker",
            meta={"username": username, "count": len(days), "days_with_activity": days_with_activity},
        )
        await s.commit()

    return {"count": len(days), "days_with_activity": days_with_activity}


async def sync_github_repos(ctx: dict) -> dict:
    """Pull owner-affiliated public repos and upsert into the projects table.

    Skips forks. Existing projects keep their sort_order/visible/status overrides
    when the user has explicitly edited them — we only update the metadata
    fields (description / lang / stars). New repos are inserted ranked by stars.
    """
    async with AsyncSessionLocal() as s:
        row = await integrations_svc.get(s, name="github")
        if row is None or row.username is None:
            return {"count": 0, "skipped": "no integration configured"}
        token = await integrations_svc.get_secret(s, name="github")
        if token is None:
            return {"count": 0, "skipped": "no token"}
        username = row.username

    try:
        repos = await github_svc.fetch_repos(token, username)
    except Exception as e:  # noqa: BLE001
        log.warning("github.repos_failed", username=username, error=str(e))
        raise
    repos = [r for r in repos if not r["fork"]]

    async with AsyncSessionLocal() as s:
        inserted = updated = 0
        for i, r in enumerate(repos):
            status = "archived" if r["archived"] else "active"
            stmt = pg_insert(Project).values(
                name=r["name"],
                description=r["description"],
                lang=r["lang"],
                stars=r["stars"],
                status=status,
                sort_order=i,
                visible=True,
            ).on_conflict_do_update(
                index_elements=[Project.name],
                set_={
                    "description": r["description"],
                    "lang": r["lang"],
                    "stars": r["stars"],
                },
            )
            res = await s.execute(stmt)
            if res.rowcount == 1 and getattr(res, "lastrowid", None) is not None:
                inserted += 1
            else:
                updated += 1
        await write_event(
            s, type="integration.github.repos_synced", actor="worker",
            meta={"username": username, "count": len(repos)},
        )
        await s.commit()

    return {"count": len(repos)}
