from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, ApiToken
from app.schemas.auth import (
    ApiTokenCreateRequest,
    ApiTokenCreateResponse,
    ApiTokenListItem,
    ApiTokenUsageItem,
)
from app.services import api_tokens as api_tokens_svc
from app.services.event_log import write_event

router = APIRouter()


@router.get("/api-tokens", response_model=list[ApiTokenListItem])
async def list_tokens(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ApiTokenListItem]:
    rows = (await s.execute(select(ApiToken).order_by(ApiToken.id))).scalars().all()
    return [
        ApiTokenListItem(
            id=r.id,
            name=r.name,
            scope=r.scope,
            last_used_at=r.last_used_at,
            usage_count=int(r.usage_count or 0),
            revoked_at=r.revoked_at,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post("/api-tokens", response_model=ApiTokenCreateResponse, dependencies=[Depends(require_scope("write"))])
async def create_token(
    req: ApiTokenCreateRequest,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> ApiTokenCreateResponse:
    row, raw = await api_tokens_svc.create(s, name=req.name, scope=req.scope)
    await write_event(
        s,
        type="api_token.created",
        actor=_admin.email,
        meta={"token_id": row.id, "name": row.name, "scope": row.scope},
    )
    await s.commit()
    return ApiTokenCreateResponse(id=row.id, name=row.name, scope=row.scope, token=raw)


@router.get(
    "/api-tokens/{token_id}/usage",
    response_model=list[ApiTokenUsageItem],
)
async def list_token_usage(
    token_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ApiTokenUsageItem]:
    """Most-recent-first per-request audit trail for one api-token (Task 29).

    Returns 404 if the token doesn't exist so the UI can distinguish a
    typo from an unused token (whose usage list is just empty).
    """
    row = (
        await s.execute(select(ApiToken).where(ApiToken.id == token_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="token not found")
    usages = await api_tokens_svc.list_usage(s, token_id=token_id, limit=limit)
    return [
        ApiTokenUsageItem(
            used_at=u.used_at,
            method=u.method,
            path=u.path,
            status_code=u.status_code,
        )
        for u in usages
    ]


@router.delete("/api-tokens/{token_id}", status_code=204, dependencies=[Depends(require_scope("write"))])
async def delete_token(
    token_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    ok = await api_tokens_svc.revoke(s, token_id=token_id)
    if not ok:
        raise HTTPException(404, "token not found or already revoked")
    await write_event(s, type="api_token.revoked", actor=_admin.email, meta={"token_id": token_id})
    await s.commit()
    return Response(status_code=204)
