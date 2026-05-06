import io
import tarfile
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, Post, Tag
from app.schemas.post import PostDetail, PostList, PostSummary
from app.services import likes
from app.services.event_log import write_event
from app.services.post_ingest import IngestError, parse_or_infer_frontmatter, upsert_post

router = APIRouter()


def _summary(p: Post, like_count: int = 0) -> PostSummary:
    return PostSummary(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
        likes=like_count,
    )


async def _detail(s: AsyncSession, p: Post) -> PostDetail:
    return PostDetail(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
        tldr=p.tldr, body=p.body_json, body_md=p.body_md,
        likes=await likes.get_count(s, post_id=p.id),
        word_count=p.word_count,
        # Task 33: lifecycle / visibility flags so the admin editor can
        # round-trip them through the PostEditor's GUI strip.
        status=p.status, scheduled_at=p.scheduled_at, featured=p.featured,
        private=p.private, comments_enabled=p.comments_enabled,
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
    counts = await likes.get_counts(s, post_ids=[p.id for p in rows])
    return PostList(
        items=[_summary(p, like_count=counts.get(p.id, 0)) for p in rows],
        total=int(total), limit=limit, offset=offset,
    )


@router.post("/posts", response_model=PostDetail, status_code=201, dependencies=[Depends(require_scope("write"))])
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
    return await _detail(s, post)


@router.get("/posts/{post_id}", response_model=PostDetail)
async def get_post(
    post_id: str,
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    return PostDetail(
        id=post.id, n=post.n, title=post.title, subtitle=post.subtitle, tag=post.tag.slug,
        date=post.date, read=post.read, lang=post.lang, summary=post.summary,
        tldr=post.tldr, body=post.body_json, body_md=post.body_md,
        likes=await likes.get_count(s, post_id=post.id),
        word_count=post.word_count,
        # Task 33: lifecycle / visibility flags.
        status=post.status, scheduled_at=post.scheduled_at, featured=post.featured,
        private=post.private, comments_enabled=post.comments_enabled,
    )


@router.patch("/posts/{post_id}", response_model=PostDetail, dependencies=[Depends(require_scope("write"))])
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
    return await _detail(s, post)


@router.delete("/posts/{post_id}", status_code=204, dependencies=[Depends(require_scope("write"))])
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


@router.post("/posts/render-preview", dependencies=[Depends(require_scope("write"))])
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


@router.post("/posts/upload", dependencies=[Depends(require_scope("write"))])
async def upload_md(
    files: list[UploadFile] = File(...),
    overwrite: bool = Query(False),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if len(files) > 20:
        raise HTTPException(status_code=413, detail="max 20 files per upload")
    results: list[dict] = []
    ok = 0
    for f in files:
        if not (f.filename and (f.filename.endswith(".md") or f.filename.endswith(".markdown"))):
            results.append({"file": f.filename, "ok": False, "status": 415, "detail": "must be .md"})
            continue
        raw_bytes = await f.read()
        if len(raw_bytes) > 1_048_576:
            results.append({"file": f.filename, "ok": False, "status": 413, "detail": "exceeds 1MB"})
            continue
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            results.append({"file": f.filename, "ok": False, "status": 422, "detail": "encoding must be utf-8"})
            continue
        try:
            fm, body_md = await parse_or_infer_frontmatter(s, raw=text, file_path=None, default_tag=None)
            post = await upsert_post(s, fm=fm, body_md=body_md, overwrite=overwrite)
            await write_event(s, type="post.created", actor=admin.email, target=post.id, meta={"via": "upload"})
            await s.flush()
            results.append({"file": f.filename, "ok": True, "post": {"id": post.id, "title": post.title}})
            ok += 1
        except IngestError as e:
            code = 409 if "already exists" in str(e) else 422
            results.append({"file": f.filename, "ok": False, "status": code, "detail": str(e)})

    failed = len(results) - ok
    if ok == len(results):
        status_code = 201
    elif ok > 0:
        status_code = 207
    else:
        status_code = 422
    return JSONResponse(
        status_code=status_code,
        content={"results": results, "summary": {"total": len(results), "ok": ok, "failed": failed}},
    )


# --- Task 42: bulk post export to tar archive ---


def _serialize_post_to_md(p: Post) -> str:
    """Render a Post as a frontmatter-prefixed markdown document.

    The frontmatter shape mirrors ``PostFrontmatter`` so the output of
    /posts/export.tar can be fed straight back through the bulk-import
    upload endpoint as a round-trip backup format.

    Strings that may contain colons / quotes are emitted as block scalars
    (``key: |``) so YAML stays unambiguous; simple strings stay inline.
    """
    def _scalar(value: str) -> str:
        # If the string contains characters YAML would mis-parse, dump it
        # as a `|` block scalar. Otherwise inline-quote it.
        if "\n" in value or value.startswith(("'", '"', "[", "{", "&", "*", "?", "|", ">", "!", "%", "#", "@", "`")):
            indented = "\n  ".join(value.split("\n"))
            return f"|\n  {indented}"
        # Always quote — defends against colons, leading dashes, etc.
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'

    lines: list[str] = ["---"]
    lines.append(f'id: "{p.id}"')
    lines.append(f'n: "{p.n}"')
    lines.append(f"title: {_scalar(p.title)}")
    if p.subtitle:
        lines.append(f"subtitle: {_scalar(p.subtitle)}")
    # Tag slug, not id — the import pipeline resolves slug → tag_id.
    tag_slug = p.tag.slug if p.tag else ""
    lines.append(f'tag: "{tag_slug}"')
    lines.append(f"date: {p.date.isoformat()}")
    if p.read:
        lines.append(f'read: "{p.read}"')
    lines.append(f'lang: "{p.lang}"')
    if p.summary:
        lines.append(f"summary: {_scalar(p.summary)}")
    if p.tldr:
        lines.append(f"tldr: {_scalar(p.tldr)}")
    lines.append(f'status: "{p.status}"')
    if p.scheduled_at is not None:
        lines.append(f"scheduled_at: {p.scheduled_at.isoformat()}")
    lines.append(f"featured: {'true' if p.featured else 'false'}")
    lines.append(f"private: {'true' if p.private else 'false'}")
    lines.append(f"comments_enabled: {'true' if p.comments_enabled else 'false'}")
    lines.append("---")
    lines.append("")
    lines.append(p.body_md or "")
    return "\n".join(lines)


@router.get("/posts.tar")
async def export_all_posts(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    """Stream every post (regardless of status / private flag) as a single
    tar archive. Each entry is `{post_id}.md` with frontmatter that round-
    trips through the existing /posts/upload endpoint.

    No pagination — owner is taking a full backup. With private/draft
    posts included, archive size scales linearly with content; for
    single-author scale this is fine.
    """
    rows = (
        await s.execute(
            select(Post).options(selectinload(Post.tag)).order_by(Post.date.desc(), Post.id)
        )
    ).scalars().all()

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for p in rows:
            md = _serialize_post_to_md(p)
            data = md.encode("utf-8")
            info = tarfile.TarInfo(name=f"{p.id}.md")
            info.size = len(data)
            # Posts have an `updated_at` via TimestampMixin — use that as
            # the tar entry mtime for reproducible ordering.
            info.mtime = int((p.updated_at or datetime.now(UTC)).timestamp())
            tar.addfile(info, io.BytesIO(data))
    body = buf.getvalue()
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    filename = f"posts-{stamp}-{len(rows)}items.tar"
    return Response(
        content=body,
        media_type="application/x-tar",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
