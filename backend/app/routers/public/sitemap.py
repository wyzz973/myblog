"""Sitemap + Atom feed for SEO and RSS readers (Task 37).

Exposes three SEO endpoints driven entirely by Post rows:
  - GET /api/sitemap.xml  — Sitemap protocol 0.9 listing
  - GET /api/feed.xml     — Atom 1.0 feed of recent published posts
  - GET /api/robots.txt   — Allow-all robots policy + Sitemap pointer (Task 38)

The XML endpoints filter to `status='published'` and `private=False`.
The site host comes from `settings.public_site_base_url` so the URLs are
absolute and crawler-friendly.
"""
from __future__ import annotations

from datetime import UTC, datetime, time
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Response
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import Post

router = APIRouter()

# Atom feed page size — small enough that a typical reader catches every
# new post but bounded so a 10k-post archive doesn't blow up the response.
FEED_LIMIT = 50


def _ts(d) -> str:
    """Render a date or datetime as ISO 8601 UTC."""
    if isinstance(d, datetime):
        if d.tzinfo is None:
            d = d.replace(tzinfo=UTC)
        return d.astimezone(UTC).isoformat()
    # plain date — assume start-of-day UTC
    return datetime.combine(d, time.min, tzinfo=UTC).isoformat()


def _xml(content: str) -> Response:
    return Response(
        content=content.encode("utf-8"),
        media_type="application/xml; charset=utf-8",
    )


@router.get("/sitemap.xml")
async def sitemap(s: AsyncSession = Depends(get_session)) -> Response:
    settings = get_settings()
    base = settings.public_site_base_url.rstrip("/")
    rows = (
        await s.execute(
            select(Post)
            .where(Post.status == "published")
            .where(Post.private.is_(False))
            .order_by(desc(Post.date))
        )
    ).scalars().all()

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        # Site root
        f"<url><loc>{escape(base)}/</loc></url>",
    ]
    for r in rows:
        loc = f"{base}/p/{r.id}"
        last = r.updated_at or r.date
        parts.append(
            "<url>"
            f"<loc>{escape(loc)}</loc>"
            f"<lastmod>{escape(_ts(last))}</lastmod>"
            "</url>"
        )
    parts.append("</urlset>")
    return _xml("".join(parts))


@router.get("/feed.xml")
async def atom_feed(s: AsyncSession = Depends(get_session)) -> Response:
    settings = get_settings()
    base = settings.public_site_base_url.rstrip("/")
    rows = (
        await s.execute(
            select(Post)
            .where(Post.status == "published")
            .where(Post.private.is_(False))
            .order_by(desc(Post.date))
            .limit(FEED_LIMIT)
        )
    ).scalars().all()

    feed_id = base + "/"
    # Latest update across the feed = newest post's updated_at, falling
    # back to the site root if there are zero published posts.
    if rows:
        head_updated = _ts(rows[0].updated_at or rows[0].date)
    else:
        head_updated = datetime.now(UTC).isoformat()

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<feed xmlns="http://www.w3.org/2005/Atom">',
        f"<title>{escape(base)}</title>",
        f"<id>{escape(feed_id)}</id>",
        f'<link rel="alternate" type="text/html" href="{escape(base)}/"/>',
        f'<link rel="self" type="application/atom+xml" href="{escape(base)}/api/feed.xml"/>',
        f"<updated>{escape(head_updated)}</updated>",
    ]
    for r in rows:
        url = f"{base}/p/{r.id}"
        when = _ts(r.updated_at or r.date)
        summary = r.summary or r.tldr or ""
        parts.append(
            "<entry>"
            f"<id>{escape(url)}</id>"
            f"<title>{escape(r.title)}</title>"
            f'<link rel="alternate" type="text/html" href="{escape(url)}"/>'
            f"<updated>{escape(when)}</updated>"
            f"<summary>{escape(summary)}</summary>"
            "</entry>"
        )
    parts.append("</feed>")
    return _xml("".join(parts))


@router.get("/robots.txt")
async def robots_txt() -> Response:
    """Allow-all crawl policy with explicit Sitemap pointer (Task 38).

    Disallows the admin API surface so crawlers don't waste budget on 401
    pages. The sitemap location uses the absolute site host so deploys
    behind a reverse proxy still get the right URL — even when this
    endpoint is mounted under /api, the sitemap reference points at the
    canonical resource.
    """
    settings = get_settings()
    base = settings.public_site_base_url.rstrip("/")
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /api/admin/\n"
        f"Sitemap: {base}/api/sitemap.xml\n"
    )
    return Response(
        content=body.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
    )
