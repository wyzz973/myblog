from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, Tag
from app.schemas.tag import TagPayload

router = APIRouter()


@router.get("/tags", response_model=list[TagPayload])
async def list_tags(s: AsyncSession = Depends(get_session)) -> list[TagPayload]:
    rows = (
        await s.execute(
            select(Tag.slug, Tag.name, func.count(Post.id))
            .outerjoin(Post, (Post.tag_id == Tag.id) & (Post.status == "published"))
            .group_by(Tag.id)
            .order_by(Tag.sort_order)
        )
    ).all()
    total = sum(r[2] for r in rows)
    out = [TagPayload(id="all", label="all", n=int(total))]
    out.extend(TagPayload(id=slug, label=name, n=int(n)) for slug, name, n in rows)
    return out
