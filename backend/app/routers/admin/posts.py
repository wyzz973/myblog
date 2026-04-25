from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Post, Tag
from app.schemas.post import PostDetail, PostList, PostSummary
from app.services.event_log import write_event
from app.services.post_ingest import IngestError, parse_or_infer_frontmatter, upsert_post

router = APIRouter()


def _summary(p: Post) -> PostSummary:
    return PostSummary(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
    )


def _detail(p: Post) -> PostDetail:
    return PostDetail(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
        tldr=p.tldr, body=p.body_json, likes=0, word_count=p.word_count,
    )


@router.get("/posts", response_model=PostList)
async def list_posts(
    status: str | None = Query(None, pattern="^(draft|published|scheduled|all)$"),
    tag: str | None = Query(None),
    q: str | None = Query(None, min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostList:
    stmt = select(Post).join(Tag)
    if status and status != "all":
        stmt = stmt.where(Post.status == status)
    if tag and tag != "all":
        stmt = stmt.where(Tag.slug == tag)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Post.title.ilike(like), Post.summary.ilike(like), Post.body_md.ilike(like))
        )
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await s.execute(stmt.order_by(Post.date.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return PostList(items=[_summary(p) for p in rows], total=int(total), limit=limit, offset=offset)


@router.post("/posts", response_model=PostDetail, status_code=201)
async def create_post(
    body: Annotated[dict, Body(..., example={"markdown": "---\nid: ...\n---\nbody"})],
    overwrite: bool = Query(False),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    md = body.get("markdown")
    if not isinstance(md, str) or not md.strip():
        raise HTTPException(status_code=422, detail="markdown body required")
    try:
        fm, body_md = await parse_or_infer_frontmatter(s, raw=md, file_path=None, default_tag=None)
        post = await upsert_post(s, fm=fm, body_md=body_md, overwrite=overwrite)
    except IngestError as e:
        raise HTTPException(status_code=409 if "already exists" in str(e) else 422, detail=str(e))
    await write_event(s, type="post.created", actor=admin.email, target=post.id)
    await s.flush()
    # reload with tag
    post = (await s.execute(select(Post).join(Tag).where(Post.id == fm.id))).scalar_one()
    return _detail(post)


@router.get("/posts/{post_id}", response_model=PostDetail)
async def get_post(
    post_id: str,
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    return _detail(post)


@router.patch("/posts/{post_id}", response_model=PostDetail)
async def patch_post(
    post_id: str,
    body: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    md = body.get("markdown")
    if not isinstance(md, str) or not md.strip():
        raise HTTPException(status_code=422, detail="markdown body required")
    try:
        fm, body_md = await parse_or_infer_frontmatter(s, raw=md, file_path=None, default_tag=None)
        if fm.id != post_id:
            raise HTTPException(status_code=422, detail="frontmatter id mismatch")
        await upsert_post(s, fm=fm, body_md=body_md, overwrite=True)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await write_event(s, type="post.updated", actor=admin.email, target=post_id)
    await s.flush()
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one()
    return _detail(post)


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> None:
    post = (await s.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(post)
    await write_event(s, type="post.deleted", actor=admin.email, target=post_id)


@router.post("/posts/render-preview")
async def render_preview(
    body: dict = Body(...),
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    md = body.get("markdown", "")
    try:
        fm, body_md = await parse_or_infer_frontmatter(s, raw=md, file_path=None, default_tag=None)
    except IngestError as e:
        return {"errors": [str(e)], "frontmatter": None, "body": []}
    from app.services.markdown_pipeline import compute_derived, parse_markdown
    try:
        blocks = parse_markdown(body_md)
    except Exception as e:
        return {"errors": [str(e)], "frontmatter": fm.model_dump(mode="json"), "body": []}
    derived = compute_derived(blocks)
    return {
        "errors": [],
        "warnings": [],
        "frontmatter": fm.model_dump(mode="json"),
        "body": blocks,
        "derived": derived,
    }
