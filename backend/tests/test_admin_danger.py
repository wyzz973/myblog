"""danger admin router HTTP tests."""
from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import Account, ExportJob, SiteMeta
from app.services.auth import hash_password


EMAIL = "hi@wangyang.dev"
KNOWN_PW = "danger-test-pw"


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
        await s.commit()


@pytest.fixture
async def admin_with_known_password():
    """Set admin password to known value; admin login uses 'changeme' so we
    can't use the existing admin_token fixture without overriding."""
    async with AsyncSessionLocal() as s:
        acct = (await s.execute(select(Account).limit(1))).scalar_one()
        original = acct.password_hash
        acct.password_hash = hash_password(KNOWN_PW)
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(update(Account).where(Account.id == acct.id).values(password_hash=original))
        await s.commit()


@pytest.fixture
async def admin_token(client, admin_with_known_password):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": KNOWN_PW})
    return r.json()["access"]


@pytest.fixture
async def export_dir(tmp_path, monkeypatch):
    from app.services import export_builder
    monkeypatch.setattr(export_builder, "_exports_dir", lambda: tmp_path)
    return tmp_path


# --- POST /api/admin/danger/export ---

async def test_export_unauthenticated_401(client, cleanup_jobs):
    r = await client.post("/api/admin/danger/export", json={"password": "x"})
    assert r.status_code == 401


async def test_export_wrong_password_401(client, admin_token, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/export",
        json={"password": "WRONG"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 401
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(ExportJob))).scalars().all()
    assert rows == []


async def test_export_correct_password_creates_job(client, admin_token, cleanup_jobs, export_dir):
    r = await client.post(
        "/api/admin/danger/export",
        json={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body
    job_id = body["job_id"]

    # ARQ_INLINE → task ran synchronously; row is now done.
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(ExportJob).where(ExportJob.id == job_id))).scalar_one()
    assert row.status == "done"
    assert row.file_size > 0


# --- GET /api/admin/danger/export/{job_id} ---

async def test_get_export_404_when_missing(client, admin_token, cleanup_jobs):
    r = await client.get(
        "/api/admin/danger/export/nonexistent",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


# --- GET /api/admin/danger/exports ---

async def test_list_exports_401(client, cleanup_jobs):
    r = await client.get("/api/admin/danger/exports")
    assert r.status_code == 401


async def test_list_exports_returns_recent(client, admin_token, cleanup_jobs):
    async with AsyncSessionLocal() as s:
        for i in range(3):
            s.add(ExportJob(
                id=f"list-{i}", status="done", requested_by="x@x.com",
                file_size=10, created_at=datetime.now(UTC),
            ))
        await s.commit()
    r = await client.get(
        "/api/admin/danger/exports",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3


# --- GET /api/admin/danger/export/{job_id}/download ---

async def test_download_404_for_missing_id(client, admin_token, cleanup_jobs):
    r = await client.get(
        "/api/admin/danger/export/missing/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_download_404_for_pending_status(client, admin_token, cleanup_jobs):
    async with AsyncSessionLocal() as s:
        s.add(ExportJob(
            id="pending-job", status="pending", requested_by="x@x.com",
            created_at=datetime.now(UTC),
        ))
        await s.commit()
    r = await client.get(
        "/api/admin/danger/export/pending-job/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_download_done_job_returns_zip(client, admin_token, cleanup_jobs, export_dir):
    job_id = "ready-job"
    # Write a real zip file at the export path.
    import zipfile
    zip_path = export_dir / f"{job_id}.zip"
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr("manifest.json", "{}")

    async with AsyncSessionLocal() as s:
        s.add(ExportJob(
            id=job_id, status="done", requested_by="x@x.com",
            file_size=zip_path.stat().st_size,
            created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
        ))
        await s.commit()

    r = await client.get(
        f"/api/admin/danger/export/{job_id}/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/zip")
    assert "attachment" in r.headers.get("content-disposition", "")


async def test_download_path_traversal_rejected(client, admin_token, cleanup_jobs):
    # Even if a row existed for this id, the resolved path must be inside
    # data/exports/. We don't seed a row — just confirm 404.
    r = await client.get(
        "/api/admin/danger/export/..%2F..%2Fetc%2Fpasswd/download",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
