"""Build a self-contained export zip of the entire site.

Layout inside the zip:
    manifest.json
    tables.json
    posts/<slug>.md
    media/<storage_path>

Tables included in tables.json: tags, projects, contacts, now_entries,
comments, site_meta, integrations, media, like_events, hit_daily, accounts,
contrib_days. Excluded: hit_events, event_log, export_jobs, posts (which
go in their own md files).
"""
from __future__ import annotations

import json
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import yaml
from sqlalchemy import select

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models import (
    Account,
    Comment,
    Contact,
    ContribDay,
    HitDaily,
    Integration,
    LikeEvent,
    Media,
    NowEntry,
    Post,
    Project,
    SiteMeta,
    Tag,
)


def _exports_dir() -> Path:
    d = get_settings().data_dir / "exports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _row_to_dict(row, columns) -> dict:
    """Serialize a SQLAlchemy row to a JSON-safe dict (datetimes -> ISO,
    dates -> ISO, JSONB stays as-is)."""
    out = {}
    for col in columns:
        v = getattr(row, col.name)
        if isinstance(v, datetime):
            out[col.name] = v.astimezone(UTC).isoformat().replace("+00:00", "Z")
        elif isinstance(v, date):
            out[col.name] = v.isoformat()
        else:
            out[col.name] = v
    return out


# Tables exported as JSON. (tag, post are special-cased.)
TABLES_FOR_JSON = [
    ("tags", Tag),
    ("projects", Project),
    ("contacts", Contact),
    ("now_entries", NowEntry),
    ("comments", Comment),
    ("site_meta", SiteMeta),
    ("integrations", Integration),
    ("media", Media),
    ("like_events", LikeEvent),
    ("hit_daily", HitDaily),
    ("accounts", Account),
    ("contrib_days", ContribDay),
]


async def build_export_zip(job_id: str) -> tuple[Path, int]:
    """Produces data/exports/<job_id>.zip; returns (path, size_bytes)."""
    final_path = _exports_dir() / f"{job_id}.zip"
    tmp_path = final_path.with_suffix(".zip.tmp")

    try:
        with zipfile.ZipFile(tmp_path, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
            async with AsyncSessionLocal() as s:
                # tag_id -> tag_slug map for post frontmatter resolution.
                tags = (await s.execute(select(Tag))).scalars().all()
                tag_id_to_slug = {t.id: t.slug for t in tags}

                # Posts -> individual md files
                posts = (await s.execute(select(Post))).scalars().all()
                post_count = len(posts)
                for p in posts:
                    fm = {
                        "id": p.id,
                        "n": p.n,
                        "title": p.title,
                        "subtitle": p.subtitle,
                        "tag": tag_id_to_slug.get(p.tag_id),
                        "date": p.date.isoformat() if p.date else None,
                        "read": p.read,
                        "lang": p.lang,
                        "summary": p.summary,
                        "tldr": p.tldr,
                        "status": p.status,
                        "featured": p.featured,
                        "private": p.private,
                        "comments_enabled": p.comments_enabled,
                        "created_at": p.created_at.astimezone(UTC).isoformat().replace("+00:00", "Z") if p.created_at else None,
                        "updated_at": p.updated_at.astimezone(UTC).isoformat().replace("+00:00", "Z") if p.updated_at else None,
                    }
                    md_body = (
                        "---\n"
                        + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False)
                        + "---\n"
                        + (p.body_md or "")
                    )
                    z.writestr(f"posts/{p.id}.md", md_body)

                # Other tables -> tables.json
                tables: dict[str, list[dict]] = {}
                table_counts: dict[str, int] = {"posts": post_count}
                for key, model in TABLES_FOR_JSON:
                    rows = (await s.execute(select(model))).scalars().all()
                    cols = list(model.__table__.columns)
                    tables[key] = [_row_to_dict(r, cols) for r in rows]
                    table_counts[key] = len(rows)
                z.writestr("tables.json", json.dumps(tables, ensure_ascii=False, default=str, indent=2))

                # site_handle for manifest hint
                sm_row = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
                site_handle = sm_row.handle

            # Walk media files
            from app.services import media_storage
            media_dir = media_storage._media_dir()
            media_count = 0
            if media_dir.exists():
                for f in media_dir.rglob("*"):
                    if f.is_file():
                        rel = f.relative_to(media_dir)
                        z.writestr(f"media/{rel.as_posix()}", f.read_bytes())
                        media_count += 1

            manifest = {
                "exporter": "p6c",
                "format_version": 1,
                "exported_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "table_counts": table_counts,
                "post_count": post_count,
                "media_count": media_count,
                "site_handle": site_handle,
            }
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))

        # Atomic rename.
        tmp_path.rename(final_path)
        size = final_path.stat().st_size
        return final_path, size
    except Exception:
        # Cleanup tmp on failure.
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise
