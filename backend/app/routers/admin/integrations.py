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
    await svc.upsert(s, name="github", username=req.username, secret=req.token)
    await s.commit()
    # trigger first sync inline (≤2s typical)
    from app.workers.tasks import sync_github_contrib
    try:
        await sync_github_contrib({})
    except Exception:  # noqa: BLE001
        pass
    row = await svc.get(s, name="github")
    return GithubIntegrationGet(
        username=row.username,
        last_synced_at=row.last_synced_at,
        last_status=row.last_status,
        last_error=row.last_error,
    )


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
    await s.commit()
    row = await svc.get(s, name="anthropic")
    return AnthropicIntegrationGet(
        model=row.extra_json.get("model"),
        last_status=row.last_status,
        last_error=row.last_error,
    )
