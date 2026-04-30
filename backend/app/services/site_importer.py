"""Site importer: consume a P6c export zip and replace site state.

Workflow:
  1. Validate manifest (exporter='p6c', format_version=1).
  2. Wipe existing site content (reuse site_wiper.wipe_site_content).
  3. Restore tables in FK-safe order from tables.json + posts/*.md.
  4. Extract media binaries into data/media/<storage_path>.
  5. Account merge: update existing admin row's password_hash/tfa fields with
     imported values (so post-import the importer can log in with the
     credentials baked into the export).

The import fails fast on validation errors before wiping. After wipe begins,
errors propagate to the caller and the DB transaction is rolled back, but
data/media/ writes are not transactional — partial media restore is possible.
"""
from __future__ import annotations

import json
import zipfile
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.services import media_storage, site_wiper

EXPECTED_EXPORTER = "p6c"
EXPECTED_FORMAT_VERSION = 1


class ImportError(Exception):
    """Raised when an export bundle fails validation or is malformed."""


# Columns that hold ISO timestamps in tables.json — convert back to datetime.
_DATETIME_COLS: dict[str, set[str]] = {
    "tags": {"created_at", "updated_at"},
    "projects": {"created_at", "updated_at"},
    "contacts": {"created_at", "updated_at"},
    "now_entries": {"created_at"},
    "comments": {"created_at"},
    "site_meta": {"created_at", "updated_at", "pending_delete_at"},
    "integrations": {"created_at", "updated_at", "last_synced_at"},
    "media": {"created_at"},
    "like_events": {"created_at"},
    "accounts": {"created_at", "updated_at"},
}

# Columns that hold ISO dates (no time) — convert back to date.
_DATE_COLS: dict[str, set[str]] = {
    "posts": {"date"},
    "site_meta": {"launched_at"},
    "like_events": {"day"},
    "hit_daily": {"date"},
    "contrib_days": {"day"},
}


def _parse_datetime(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _parse_date(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    return date.fromisoformat(str(v))


def _coerce_row(table: str, row: dict[str, Any]) -> dict[str, Any]:
    """Convert ISO strings → datetime/date for SQLAlchemy column types."""
    out = dict(row)
    for col in _DATETIME_COLS.get(table, set()):
        if col in out:
            out[col] = _parse_datetime(out[col])
    for col in _DATE_COLS.get(table, set()):
        if col in out:
            out[col] = _parse_date(out[col])
    return out


def _validate_manifest(manifest: dict[str, Any]) -> None:
    exporter = manifest.get("exporter")
    fmt = manifest.get("format_version")
    if exporter != EXPECTED_EXPORTER:
        raise ImportError(
            f"unsupported exporter: {exporter!r} (expected {EXPECTED_EXPORTER!r})"
        )
    if fmt != EXPECTED_FORMAT_VERSION:
        raise ImportError(
            f"unsupported format_version: {fmt!r} (expected {EXPECTED_FORMAT_VERSION})"
        )


def _safe_extract_path(media_dir: Path, member_name: str) -> Path | None:
    """Return resolved path inside media_dir if `member_name` is safe; None otherwise.

    `member_name` is the zip entry path with the leading "media/" already stripped.
    Rejects absolute paths and ../ traversal.
    """
    rel = Path(member_name)
    if rel.is_absolute():
        return None
    candidate = (media_dir / rel).resolve()
    media_dir_resolved = media_dir.resolve()
    try:
        candidate.relative_to(media_dir_resolved)
    except ValueError:
        return None
    return candidate


def _parse_post_md(md_text: str) -> tuple[dict[str, Any], str]:
    """Parse a `posts/<id>.md` file: split YAML frontmatter from body markdown."""
    if not md_text.startswith("---\n"):
        raise ImportError("post md missing frontmatter")
    rest = md_text[4:]
    end = rest.find("\n---\n")
    if end < 0:
        raise ImportError("post md frontmatter not terminated")
    fm_block = rest[:end]
    body = rest[end + 5:]  # skip "\n---\n"
    fm = yaml.safe_load(fm_block) or {}
    if not isinstance(fm, dict):
        raise ImportError("post md frontmatter is not a mapping")
    return fm, body


async def import_site_from_zip(
    s: AsyncSession, *, zip_bytes: bytes
) -> dict[str, int]:
    """Validate manifest, wipe, then re-create rows + media from the bundle.

    Returns {tables_imported, posts_imported, media_imported}.
    Raises ImportError on validation failures.
    """
    try:
        z = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ImportError(f"invalid zip: {e}") from e

    with z:
        names = set(z.namelist())
        if "manifest.json" not in names:
            raise ImportError("invalid export bundle: missing manifest")
        if "tables.json" not in names:
            raise ImportError("invalid export bundle: missing tables.json")

        try:
            manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ImportError(f"invalid manifest.json: {e}") from e
        _validate_manifest(manifest)

        try:
            tables = json.loads(z.read("tables.json").decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise ImportError(f"invalid tables.json: {e}") from e
        if not isinstance(tables, dict):
            raise ImportError("tables.json must be an object")

        # Pre-parse posts/*.md so we fail BEFORE wiping if the bundle is bad.
        post_files: list[tuple[dict[str, Any], str]] = []
        for name in sorted(names):
            if name.startswith("posts/") and name.endswith(".md"):
                try:
                    md_text = z.read(name).decode("utf-8")
                except UnicodeDecodeError as e:
                    raise ImportError(f"post {name}: not utf-8: {e}") from e
                post_files.append(_parse_post_md(md_text))

        # Pre-validate media entry paths for zip-slip BEFORE any state mutation.
        media_dir = media_storage._media_dir()
        media_entries: list[tuple[str, Path, bytes]] = []
        for name in names:
            if not name.startswith("media/"):
                continue
            # Skip directory entries (zip can have them).
            if name.endswith("/"):
                continue
            inner = name[len("media/"):]
            target = _safe_extract_path(media_dir, inner)
            if target is None:
                raise ImportError(f"unsafe media entry path: {name}")
            media_entries.append((inner, target, z.read(name)))

        # All validation passed — proceed with wipe + restore.
        await site_wiper.wipe_site_content(s)
        await s.flush()

        tables_imported = 0
        posts_imported = 0
        media_imported = 0

        # 1. tags (posts FK to tags.id by id)
        rows = tables.get("tags", []) or []
        if rows:
            await s.execute(
                insert(Tag),
                [_coerce_row("tags", r) for r in rows],
            )
            tables_imported += 1

        # 2. projects (PK=name)
        rows = tables.get("projects", []) or []
        if rows:
            await s.execute(
                insert(Project),
                [_coerce_row("projects", r) for r in rows],
            )
            tables_imported += 1

        # 3. posts (from posts/*.md). Resolve `tag` slug → tag_id.
        if post_files:
            tag_rows = (await s.execute(select(Tag))).scalars().all()
            slug_to_id = {t.slug: t.id for t in tag_rows}
            post_inserts: list[dict[str, Any]] = []
            for fm, body in post_files:
                tag_slug = fm.get("tag")
                tag_id = slug_to_id.get(tag_slug) if tag_slug else None
                if tag_id is None:
                    raise ImportError(
                        f"post {fm.get('id')!r}: tag slug {tag_slug!r} not found"
                    )
                row = {
                    "id": fm.get("id"),
                    "n": fm.get("n", "0"),
                    "title": fm.get("title", ""),
                    "subtitle": fm.get("subtitle"),
                    "tag_id": tag_id,
                    "date": _parse_date(fm.get("date")),
                    "read": fm.get("read"),
                    "lang": fm.get("lang", "zh"),
                    "summary": fm.get("summary"),
                    "tldr": fm.get("tldr"),
                    "body_md": body,
                    "body_json": [],
                    "word_count": 0,
                    "status": fm.get("status", "draft"),
                    "featured": bool(fm.get("featured", False)),
                    "private": bool(fm.get("private", False)),
                    "comments_enabled": bool(fm.get("comments_enabled", True)),
                    "created_at": _parse_datetime(fm.get("created_at"))
                                  or datetime.now(UTC),
                    "updated_at": _parse_datetime(fm.get("updated_at"))
                                  or datetime.now(UTC),
                }
                post_inserts.append(row)
            await s.execute(insert(Post), post_inserts)
            posts_imported = len(post_inserts)

        # 4. comments (FK posts; self-FK parent_id; insert in id order so parents land first)
        rows = tables.get("comments", []) or []
        if rows:
            ordered = sorted(rows, key=lambda r: r.get("id", 0))
            await s.execute(
                insert(Comment),
                [_coerce_row("comments", r) for r in ordered],
            )
            tables_imported += 1

        # 5. contacts
        rows = tables.get("contacts", []) or []
        if rows:
            await s.execute(
                insert(Contact),
                [_coerce_row("contacts", r) for r in rows],
            )
            tables_imported += 1

        # 6. now_entries
        rows = tables.get("now_entries", []) or []
        if rows:
            await s.execute(
                insert(NowEntry),
                [_coerce_row("now_entries", r) for r in rows],
            )
            tables_imported += 1

        # 7. contrib_days
        rows = tables.get("contrib_days", []) or []
        if rows:
            await s.execute(
                insert(ContribDay),
                [_coerce_row("contrib_days", r) for r in rows],
            )
            tables_imported += 1

        # 8. media (rows; binaries land separately under data/media/)
        rows = tables.get("media", []) or []
        if rows:
            await s.execute(
                insert(Media),
                [_coerce_row("media", r) for r in rows],
            )
            tables_imported += 1

        # 9. site_meta — singleton row (UPDATE, not INSERT). Skip 'id'.
        sm_rows = tables.get("site_meta", []) or []
        if sm_rows:
            sm_row = _coerce_row("site_meta", sm_rows[0])
            sm_row.pop("id", None)
            # avatar_path was a legacy free-form column on site_meta, dropped
            # after avatar_id (FK to media) became authoritative. Pre-drop
            # exports may still carry it; ignore on import.
            sm_row.pop("avatar_path", None)
            # Preserve admin's deletion-cancel state: pending_delete_at on the
            # imported snapshot is irrelevant to the freshly-imported site.
            sm_row["pending_delete_at"] = None
            await s.execute(
                update(SiteMeta).where(SiteMeta.id == 1).values(**sm_row)
            )
            tables_imported += 1

        # 10. integrations
        rows = tables.get("integrations", []) or []
        if rows:
            await s.execute(
                insert(Integration),
                [_coerce_row("integrations", r) for r in rows],
            )
            tables_imported += 1

        # 11. like_events (FK posts)
        rows = tables.get("like_events", []) or []
        if rows:
            await s.execute(
                insert(LikeEvent),
                [_coerce_row("like_events", r) for r in rows],
            )
            tables_imported += 1

        # 12. hit_daily (FK posts via post_id, ON DELETE SET NULL)
        rows = tables.get("hit_daily", []) or []
        if rows:
            await s.execute(
                insert(HitDaily),
                [_coerce_row("hit_daily", r) for r in rows],
            )
            tables_imported += 1

        # 13. accounts — singleton merge: keep existing admin row, copy auth fields
        #     from the imported account so the imported password works post-import.
        acct_rows = tables.get("accounts", []) or []
        if acct_rows:
            imp = _coerce_row("accounts", acct_rows[0])
            existing = (
                await s.execute(select(Account).where(Account.id == 1))
            ).scalar_one_or_none()
            merge_values = {
                "email": imp.get("email"),
                "password_hash": imp.get("password_hash"),
                "tfa_secret_encrypted": imp.get("tfa_secret_encrypted"),
                "tfa_enabled": bool(imp.get("tfa_enabled", False)),
                "magic_link_enabled": bool(imp.get("magic_link_enabled", False)),
            }
            if existing is None:
                await s.execute(
                    insert(Account).values(id=1, **merge_values)
                )
            else:
                await s.execute(
                    update(Account).where(Account.id == 1).values(**merge_values)
                )
            tables_imported += 1

        # 14. Resequence Postgres autoincrement sequences for tables we restored
        #     with explicit ids. Otherwise next INSERT collides on PK.
        await _resync_sequences(s)

        # Now extract media binaries to disk (after DB rows committed in caller).
        media_dir.mkdir(parents=True, exist_ok=True)
        for _inner, target, blob in media_entries:
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(blob)
            tmp.rename(target)
            media_imported += 1

    return {
        "tables_imported": tables_imported,
        "posts_imported": posts_imported,
        "media_imported": media_imported,
    }


async def _resync_sequences(s: AsyncSession) -> None:
    """After bulk INSERTs with explicit ids, reset Postgres sequences for
    autoincrement columns so subsequent inserts don't collide."""
    from sqlalchemy import text

    # (table, pk column) pairs whose PK is a SERIAL/IDENTITY in 0001+0007 schema.
    sequences = [
        ("tags", "id"),
        ("comments", "id"),
        ("contacts", "id"),
        ("now_entries", "id"),
        ("media", "id"),
        ("like_events", "id"),
    ]
    for tbl, col in sequences:
        await s.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{tbl}', '{col}'), "
                f"COALESCE((SELECT MAX({col}) FROM {tbl}), 0) + 1, false)"
            )
        )
