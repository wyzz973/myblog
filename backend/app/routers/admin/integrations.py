from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account
from app.schemas.integration import (
    AnthropicIntegrationGet,
    AnthropicIntegrationPut,
    GithubIntegrationGet,
    GithubIntegrationPut,
)
from app.services import github as github_svc
from app.services import integrations as svc
from app.services import pet_llm as pet_svc
from app.services.event_log import write_event

router = APIRouter()


@router.get("/integrations/github", response_model=GithubIntegrationGet)
async def get_github(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> GithubIntegrationGet:
    row = await svc.get(s, name="github")
    if row is None:
        return GithubIntegrationGet()
    return GithubIntegrationGet(
        username=row.username,
        last_synced_at=row.last_synced_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.put(
    "/integrations/github",
    response_model=GithubIntegrationGet,
    dependencies=[Depends(require_scope("write"))],
)
async def put_github(
    req: GithubIntegrationPut,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> GithubIntegrationGet:
    login = await github_svc.ping(req.token)
    if login is None:
        raise HTTPException(422, "github token invalid")
    # Tx 1: upsert + tested event (atomic — paired data + audit)
    await svc.upsert(s, name="github", username=req.username, secret=req.token)
    await write_event(
        s, type="integration.github.tested", actor=_admin.email,
        meta={"username": req.username},
    )
    await s.commit()

    # Trigger first sync inline (≤2s typical). Worker uses its own sessions.
    sync_meta: dict = {"username": req.username}
    sync_failed = False
    try:
        from app.workers.tasks import sync_github_contrib
        result = await sync_github_contrib({})
        sync_meta.update(result)
    except Exception as e:  # noqa: BLE001
        sync_failed = True
        sync_meta["error"] = str(e)[:512]

    # Tx 2: sync outcome event (atomic with itself; prior tested commit is durable)
    event_type = (
        "integration.github.failed" if sync_failed else "integration.github.synced"
    )
    await write_event(s, type=event_type, actor=_admin.email, meta=sync_meta)
    await s.commit()

    row = await svc.get(s, name="github")
    return GithubIntegrationGet(
        username=row.username,
        last_synced_at=row.last_synced_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.post("/integrations/github/sync", dependencies=[Depends(require_scope("write"))])
async def sync_github(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    from app.workers.tasks import sync_github_contrib, sync_github_repos
    try:
        contrib = await sync_github_contrib({})
        repos = await sync_github_repos({})
    except Exception as e:  # noqa: BLE001
        await write_event(
            s, type="integration.github.failed", actor=_admin.email,
            meta={"manual": True, "error": str(e)[:512]},
        )
        await s.commit()
        raise HTTPException(502, "github sync failed") from e
    row = await svc.get(s, name="github")
    await write_event(
        s, type="integration.github.synced", actor=_admin.email,
        meta={"manual": True, **contrib, "repos": repos.get("count", 0)},
    )
    await s.commit()
    return {
        **contrib,
        "repos_synced": repos.get("count", 0),
        "last_synced_at": row.last_synced_at.isoformat() if row and row.last_synced_at else None,
    }


@router.get("/integrations/anthropic", response_model=AnthropicIntegrationGet)
async def get_anthropic(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> AnthropicIntegrationGet:
    row = await svc.get(s, name="anthropic")
    if row is None:
        return AnthropicIntegrationGet()
    return AnthropicIntegrationGet(
        model=row.extra_json.get("model"),
        last_status=row.last_status,
        last_error=row.last_error,
    )


@router.put(
    "/integrations/anthropic",
    response_model=AnthropicIntegrationGet,
    dependencies=[Depends(require_scope("write"))],
)
async def put_anthropic(
    req: AnthropicIntegrationPut,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> AnthropicIntegrationGet:
    ok = await pet_svc.ping(req.api_key, req.model or "claude-haiku-4-5-20251001")
    if not ok:
        raise HTTPException(422, "anthropic api key invalid")
    extras = {"model": req.model} if req.model else {}
    await svc.upsert(s, name="anthropic", username=None, secret=req.api_key, extra=extras)
    await svc.set_status(s, name="anthropic", status="ok", error=None)
    await write_event(s, type="integration.anthropic.tested", actor=_admin.email, meta={"ok": True})
    await s.commit()
    row = await svc.get(s, name="anthropic")
    return AnthropicIntegrationGet(
        model=row.extra_json.get("model"),
        last_status=row.last_status,
        last_error=row.last_error,
    )
