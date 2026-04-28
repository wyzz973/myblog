"""export_builder service unit tests."""
from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import (
    Media,
    Post,
    Tag,
)
from app.services import export_builder


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def export_dir(tmp_path, monkeypatch):
    """Override the exports directory so each test writes into tmp_path."""
    from app.services import export_builder as eb
    monkeypatch.setattr(eb, "_exports_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
async def cleanup_post():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Post).where(Post.id.like("ebtest-%")))
        await s.execute(delete(Media).where(Media.storage_path.like("ee/%")))
        await s.commit()


async def test_build_export_zip_has_required_top_level(export_dir, cleanup_post):
    job_id = "ebtest-empty"
    path, size = await export_builder.build_export_zip(job_id)
    assert path == export_dir / f"{job_id}.zip"
    assert path.exists()
    assert size > 0
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    assert "manifest.json" in names
    assert "tables.json" in names


async def test_build_export_zip_with_post_writes_md(export_dir, cleanup_post):
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        s.add(Post(
            id="ebtest-howdy", n="1", title="Howdy",
            subtitle="hi", date=datetime.now(UTC).date(),
            read="3", lang="en", summary="", tldr="",
            body_md="# Hello\n\nworld", body_json=[],
            word_count=2, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=tag.id,
        ))
        await s.commit()

    job_id = "ebtest-with-post"
    path, _ = await export_builder.build_export_zip(job_id)
    with zipfile.ZipFile(path) as z:
        md = z.read("posts/ebtest-howdy.md").decode()
    # Frontmatter present
    assert md.startswith("---\n")
    assert "title: Howdy" in md
    # Tag resolved to slug
    assert f"tag: {tag.slug}" in md
    # Body included
    assert "# Hello" in md


async def test_build_export_zip_tables_json_excludes_internal(export_dir, cleanup_post):
    job_id = "ebtest-tables"
    path, _ = await export_builder.build_export_zip(job_id)
    with zipfile.ZipFile(path) as z:
        tables = json.loads(z.read("tables.json"))
    # Posts are serialized as md files, NOT in tables.json
    assert "posts" not in tables
    # event_log, hit_events, export_jobs excluded
    assert "event_log" not in tables
    assert "hit_events" not in tables
    assert "export_jobs" not in tables
    # accounts is included
    assert "accounts" in tables
    # tags included
    assert "tags" in tables


async def test_build_export_zip_accounts_includes_password_hash(export_dir, cleanup_post):
    job_id = "ebtest-acct"
    path, _ = await export_builder.build_export_zip(job_id)
    with zipfile.ZipFile(path) as z:
        tables = json.loads(z.read("tables.json"))
    assert tables["accounts"], "accounts list must not be empty"
    assert "password_hash" in tables["accounts"][0]
    assert tables["accounts"][0]["password_hash"]  # non-empty


async def test_build_export_zip_media_binary_preserved(export_dir, cleanup_post, tmp_path, monkeypatch):
    """Write a real PNG into MEDIA_DIR + a Media row, run export, verify zip
    contains byte-identical media payload."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)
    media_dir = tmp_path
    bucket = media_dir / "ee"
    bucket.mkdir(parents=True, exist_ok=True)
    buf = BytesIO()
    Image.new("RGB", (10, 8), "blue").save(buf, format="PNG")
    png_bytes = buf.getvalue()
    storage_path = "ee/ebtest-banner.png"
    (media_dir / storage_path).write_bytes(png_bytes)

    async with AsyncSessionLocal() as s:
        s.add(Media(
            filename="banner.png", storage_path=storage_path,
            mime_type="image/png", size=len(png_bytes), width=10, height=8,
            alt=None, created_at=datetime.now(UTC),
        ))
        await s.commit()

    job_id = "ebtest-media"
    path, _ = await export_builder.build_export_zip(job_id)
    with zipfile.ZipFile(path) as z:
        in_zip = z.read(f"media/{storage_path}")
    assert in_zip == png_bytes


async def test_build_export_zip_manifest_has_table_counts(export_dir, cleanup_post):
    job_id = "ebtest-manifest"
    path, _ = await export_builder.build_export_zip(job_id)
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("manifest.json"))
    assert manifest["exporter"] == "p6c"
    assert manifest["format_version"] == 1
    assert "table_counts" in manifest
    assert "exported_at" in manifest
