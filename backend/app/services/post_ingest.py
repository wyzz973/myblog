"""Ingest a markdown document (with or without frontmatter) into the posts table."""
from __future__ import annotations

import re
import json
from datetime import date
from pathlib import Path

import frontmatter
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, Tag
from app.services.frontmatter_schema import PostFrontmatter
from app.services.markdown_pipeline import compute_derived, parse_markdown

SENSITIVE = re.compile(r"^(accounts?|secrets?|password?|credential?|.*\.env)", re.IGNORECASE)


class IngestError(ValueError):
    pass


def is_sensitive(path: Path) -> bool:
    return bool(SENSITIVE.match(path.stem))


def _slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:64]


def _slug_with_fallback(*candidates: str) -> str:
    """Try each candidate string, return first non-empty slug."""
    for c in candidates:
        s = _slugify(c)
        if s:
            return s
    return "post"


def _detect_lang(text: str) -> str:
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if cjk / max(1, len(text)) > 0.3 else "en"


def _quote_plain_frontmatter_scalars(raw: str) -> str | None:
    """Quote top-level plain scalar values that contain a colon.

    Authors commonly write values like ``summary: release notes:`` in the
    admin editor. YAML requires that scalar to be quoted, but rejecting the
    whole post is unnecessarily sharp. This fallback only rewrites simple
    top-level ``key: value`` lines and leaves nested or already-structured YAML
    alone.
    """
    if not raw.startswith("---"):
        return None

    lines = raw.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return None

    close_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() in {"---", "..."}:
            close_idx = i
            break
    if close_idx is None:
        return None

    changed = False
    fixed = lines[:]
    for i in range(1, close_idx):
        line = fixed[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or line[:1].isspace():
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):(\s*)(.*?)(\r?\n)?$", line)
        if not match:
            continue
        key, spacing, value, newline = match.groups()
        value = value.strip()
        if ":" not in value or not value:
            continue
        if value[0] in {"'", '"', "[", "{", "|", ">", "!", "&", "*"}:
            continue
        fixed[i] = f"{key}:{spacing}{json.dumps(value, ensure_ascii=False)}{newline or ''}"
        changed = True

    return "".join(fixed) if changed else None


def _extract_first_h1(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return None


async def _next_n(session: AsyncSession) -> str:
    max_n = (await session.execute(select(func.max(Post.n)))).scalar() or "000"
    try:
        return f"{int(max_n) + 1:03d}"
    except ValueError:
        return "001"


async def parse_or_infer_frontmatter(
    session: AsyncSession,
    *,
    raw: str,
    file_path: Path | None,
    default_tag: str | None,
) -> tuple[PostFrontmatter, str]:
    """Returns (validated_frontmatter, body_md).

    If the document has no frontmatter, infer the required fields from the
    body (first H1 → title, filename → id, mtime → date, char ratio → lang)
    and the caller-supplied default_tag.
    """
    try:
        parsed = frontmatter.loads(raw)
    except Exception as e:  # noqa: BLE001 - normalize parser errors for admin/API callers.
        fixed_raw = _quote_plain_frontmatter_scalars(raw)
        if fixed_raw is None:
            raise IngestError(f"frontmatter invalid: {e}") from e
        try:
            parsed = frontmatter.loads(fixed_raw)
        except Exception as e2:  # noqa: BLE001 - keep API errors structured.
            raise IngestError(f"frontmatter invalid: {e2}") from e2
    body = parsed.content
    meta = dict(parsed.metadata)

    if not meta:
        title = _extract_first_h1(body)
        if title is None:
            raise IngestError("no frontmatter and no H1 to infer title from")
        if file_path is not None:
            meta["id"] = _slug_with_fallback(file_path.stem, title)
            meta["date"] = date.fromtimestamp(file_path.stat().st_mtime).isoformat()
        else:
            meta["id"] = _slug_with_fallback(title)
            meta["date"] = date.today().isoformat()
        meta["title"] = title
        meta["n"] = await _next_n(session)
        meta["lang"] = _detect_lang(body)
        if default_tag is None:
            raise IngestError(
                "no frontmatter present; supply --default-tag <slug> or add frontmatter"
            )
        meta["tag"] = default_tag

    try:
        fm = PostFrontmatter(**meta)
    except ValidationError as e:
        # Compact the Pydantic error list into a single line for CLI output.
        details = "; ".join(
            f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()
        )
        raise IngestError(f"frontmatter invalid: {details}") from e

    tag_row = (await session.execute(select(Tag).where(Tag.slug == fm.tag))).scalar_one_or_none()
    if tag_row is None:
        raise IngestError(f"tag '{fm.tag}' not found in tags table; create it first")

    return fm, body


async def upsert_post(
    session: AsyncSession,
    *,
    fm: PostFrontmatter,
    body_md: str,
    overwrite: bool,
) -> Post:
    blocks = parse_markdown(body_md)
    derived = compute_derived(blocks)
    tag_row = (await session.execute(select(Tag).where(Tag.slug == fm.tag))).scalar_one()

    existing = (await session.execute(select(Post).where(Post.id == fm.id))).scalar_one_or_none()
    if existing is not None and not overwrite:
        raise IngestError(f"post id '{fm.id}' already exists (pass --overwrite to replace)")

    if existing is None:
        post = Post(id=fm.id, tag_id=tag_row.id, body_md=body_md, body_json=blocks)
        session.add(post)
    else:
        post = existing
        post.tag_id = tag_row.id
        post.body_md = body_md
        post.body_json = blocks

    post.n = fm.n
    post.title = fm.title
    post.subtitle = fm.subtitle
    post.date = fm.date
    post.read = fm.read or derived["read"]
    post.lang = fm.lang
    post.summary = fm.summary or derived["summary"]
    post.tldr = fm.tldr
    post.status = fm.status
    post.scheduled_at = fm.scheduled_at
    post.featured = fm.featured
    post.private = fm.private
    post.comments_enabled = fm.comments_enabled
    post.word_count = derived["word_count"]
    return post
