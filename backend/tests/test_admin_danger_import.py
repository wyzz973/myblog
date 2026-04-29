"""danger admin import endpoint HTTP tests."""
from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import (
    Account,
    Contact,
    ExportJob,
    Media,
    NowEntry,
    Post,
    SiteMeta,
    Tag,
)
from app.services import export_builder
from app.services.auth import hash_password

EMAIL = "hi@wangyang.dev"
KNOWN_PW = "import-test-pw"


@pytest.fixture(autouse=True)
def _force_arq_inline(monkeypatch):
    from app.config import get_settings
    monkeypatch.setenv("ARQ_INLINE", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def cleanup_jobs():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(ExportJob))
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=None))
        # The round-trip tests seed Post/Contact/NowEntry/Media rows that the
        # import then wipes + restores. If a test fails mid-way these rows can
        # linger and (notably) violate the partial unique index on
        # now_entries(is_current) for the next run. Best-effort scrub.
        await s.execute(delete(NowEntry))
        await s.execute(delete(Post).where(Post.id.like("round-trip%")))
        await s.execute(delete(Media).where(Media.storage_path.like("rt/%")))
        await s.execute(delete(Contact).where(Contact.label.like("rt-%")))
        await s.commit()


@pytest.fixture
async def admin_with_known_password():
    """Set admin password to a known value, snapshotting for restore."""
    async with AsyncSessionLocal() as s:
        acct = (await s.execute(select(Account).limit(1))).scalar_one()
        original = acct.password_hash
        acct.password_hash = hash_password(KNOWN_PW)
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(Account).where(Account.id == acct.id).values(password_hash=original)
        )
        await s.commit()


@pytest.fixture
async def admin_token(client, admin_with_known_password):
    r = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": KNOWN_PW}
    )
    return r.json()["access"]


@pytest.fixture
async def isolated_dirs(tmp_path, monkeypatch):
    """Redirect both _exports_dir and _media_dir into tmp_path so the export
    we build (and the import that consumes it) doesn't pollute the real
    data/ folder."""
    from app.services import media_storage
    exports = tmp_path / "exports"
    exports.mkdir()
    media = tmp_path / "media"
    media.mkdir()
    monkeypatch.setattr(export_builder, "_exports_dir", lambda: exports)
    monkeypatch.setattr(media_storage, "_media_dir", lambda: media)
    return {"exports": exports, "media": media}


def _build_zip_from_dict(entries: dict[str, bytes | str]) -> bytes:
    """Helper: create an in-memory zip from a {name: content} dict."""
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in entries.items():
            if isinstance(content, str):
                z.writestr(name, content)
            else:
                z.writestr(name, content)
    return buf.getvalue()


# --- 401 paths ---

async def test_import_unauthenticated_401(client, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", b"PK\x03\x04", "application/zip")},
        data={"password": "x"},
    )
    assert r.status_code == 401


async def test_import_missing_password_form_field(client, admin_token, cleanup_jobs):
    """No password form field at all → FastAPI validation 422."""
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", b"PK\x03\x04", "application/zip")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_import_wrong_password_401(client, admin_token, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", b"PK\x03\x04PK\x05\x06\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00", "application/zip")},
        data={"password": "WRONG"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 401


# --- 422 invalid bundle paths ---

async def test_import_invalid_zip_random_bytes_422(client, admin_token, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", b"this is not a zip", "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_import_zip_missing_manifest_422(client, admin_token, cleanup_jobs):
    bundle = _build_zip_from_dict({"tables.json": "{}"})
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", bundle, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422
    assert "manifest" in r.json()["detail"].lower()


async def test_import_zip_missing_tables_422(client, admin_token, cleanup_jobs):
    manifest = {"exporter": "p6c", "format_version": 1, "exported_at": "2026-04-28T00:00:00Z"}
    bundle = _build_zip_from_dict({"manifest.json": json.dumps(manifest)})
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", bundle, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_import_wrong_format_version_422(client, admin_token, cleanup_jobs):
    manifest = {"exporter": "p6c", "format_version": 99, "exported_at": "2026-04-28T00:00:00Z"}
    bundle = _build_zip_from_dict({
        "manifest.json": json.dumps(manifest),
        "tables.json": "{}",
    })
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", bundle, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422
    assert "format_version" in r.json()["detail"]


async def test_import_wrong_exporter_422(client, admin_token, cleanup_jobs):
    manifest = {"exporter": "evil", "format_version": 1, "exported_at": "2026-04-28T00:00:00Z"}
    bundle = _build_zip_from_dict({
        "manifest.json": json.dumps(manifest),
        "tables.json": "{}",
    })
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", bundle, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_import_zip_slip_rejected_422(client, admin_token, cleanup_jobs, isolated_dirs, reseed_after):
    """A media entry with `../../etc/passwd` must be rejected and the file not extracted."""
    manifest = {"exporter": "p6c", "format_version": 1, "exported_at": "2026-04-28T00:00:00Z"}
    bundle = _build_zip_from_dict({
        "manifest.json": json.dumps(manifest),
        "tables.json": "{}",
        "media/../../etc/passwd-attack": b"pwned",
    })
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("x.zip", bundle, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422
    # File must not have been written outside media_dir.
    media_dir = isolated_dirs["media"]
    # Look anywhere in the parent for the suspicious filename.
    for parent in [media_dir, *media_dir.parents]:
        for hit in parent.rglob("passwd-attack"):
            pytest.fail(f"zip-slip leaked file at {hit}")


# --- happy path (round-trip via export_builder.build_export_zip) ---

async def test_import_round_trip_restores_rows(
    client, admin_token, cleanup_jobs, isolated_dirs, reseed_after
):
    """Build a real export via P6c export_builder, then import it. Verify the
    posts/tags/media survived round-trip."""
    media_dir = isolated_dirs["media"]

    # Seed data into the live DB so the export captures it.
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        s.add(Post(
            id="round-trip-1", n="42", title="Round Trip",
            subtitle="hi", date=datetime.now(UTC).date(),
            read="2", lang="en", summary="sum", tldr="tldr",
            body_md="# Round\n\nbody", body_json=[],
            word_count=2, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=tag.id,
        ))
        s.add(Contact(label="rt-x", value="x@x.com", href="mailto:x@x.com",
                      visible=True, sort_order=0))
        s.add(NowEntry(body_md="rt now", listening=None, reading=None,
                       is_current=True, created_at=datetime.now(UTC)))
        # Media row + file
        bucket = media_dir / "rt"
        bucket.mkdir(parents=True, exist_ok=True)
        png = BytesIO()
        Image.new("RGB", (4, 4), "red").save(png, format="PNG")
        png_bytes = png.getvalue()
        (bucket / "rt-asset.png").write_bytes(png_bytes)
        s.add(Media(
            filename="asset.png", storage_path="rt/rt-asset.png",
            mime_type="image/png", size=len(png_bytes), width=4, height=4,
            alt=None, created_at=datetime.now(UTC),
        ))
        await s.commit()

    # Build the export.
    job_id = "rt-job"
    zip_path, _ = await export_builder.build_export_zip(job_id)
    zip_bytes = zip_path.read_bytes()

    # Wipe media file (simulate disaster) — import should re-create it.
    (media_dir / "rt" / "rt-asset.png").unlink()

    # Import. Multipart upload.
    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["posts_imported"] >= 1
    assert body["media_imported"] >= 1
    assert body["tables_imported"] >= 1

    # Verify post row survived round-trip.
    async with AsyncSessionLocal() as s:
        post = (
            await s.execute(select(Post).where(Post.id == "round-trip-1"))
        ).scalar_one_or_none()
        assert post is not None
        assert post.title == "Round Trip"
        assert "Round" in post.body_md

        # Tag still resolved via slug.
        tag_after = (
            await s.execute(select(Tag).where(Tag.id == post.tag_id))
        ).scalar_one()
        assert tag_after.slug == tag.slug

        # Media row + file present.
        media_rows = (
            await s.execute(select(Media).where(Media.storage_path == "rt/rt-asset.png"))
        ).scalars().all()
        assert len(media_rows) == 1
    assert (media_dir / "rt" / "rt-asset.png").exists()
    assert (media_dir / "rt" / "rt-asset.png").read_bytes() == png_bytes


async def test_import_replaces_admin_password_hash(
    client, admin_token, cleanup_jobs, isolated_dirs, reseed_after
):
    """The imported account's password_hash must overwrite the live admin's
    (otherwise the importer is locked out unless they remember the imported
    password). Round-trip with the same password works because both hashes
    derive from the same plaintext."""
    job_id = "rt-acct"
    zip_path, _ = await export_builder.build_export_zip(job_id)
    zip_bytes = zip_path.read_bytes()

    # Snapshot current admin row.
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(Account).where(Account.id == 1))).scalar_one()
        before_email = before.email
        before_hash = before.password_hash

    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text

    async with AsyncSessionLocal() as s:
        after = (await s.execute(select(Account).where(Account.id == 1))).scalar_one()
    # Email + hash both come from the imported snapshot (which is the SAME
    # data we just exported, so they match the pre-import values).
    assert after.email == before_email
    assert after.password_hash == before_hash


async def test_import_then_login_with_imported_password(
    client, admin_token, cleanup_jobs, isolated_dirs, reseed_after
):
    """After import, login must succeed with the password that was current at
    export-time (i.e. KNOWN_PW)."""
    job_id = "rt-login"
    zip_path, _ = await export_builder.build_export_zip(job_id)
    zip_bytes = zip_path.read_bytes()

    r = await client.post(
        "/api/admin/danger/import",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        data={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text

    # Try login with the imported password.
    r2 = await client.post(
        "/api/admin/auth/login", json={"email": EMAIL, "password": KNOWN_PW}
    )
    assert r2.status_code == 200
    assert "access" in r2.json()
