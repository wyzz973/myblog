"""danger service unit tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import Account, ExportJob, SiteMeta
from app.services import danger
from app.services.auth import hash_password


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture(autouse=True)
def _register_noop_export_task(monkeypatch):
    """Stub the build_export_task in inline-mode registry so danger
    service tests don't depend on the task implementation."""
    # Force inline mode (the session conftest may have cached arq_inline=False
    # before ARQ_INLINE was set in the env).
    monkeypatch.setenv("ARQ_INLINE", "true")
    from app.config import get_settings
    get_settings.cache_clear()

    from app.workers import queue as q
    async def _noop(ctx, **kwargs):
        return {"stub": True}
    prev = q._TASK_REGISTRY.get("build_export_task")
    q._TASK_REGISTRY["build_export_task"] = _noop
    yield
    if prev is None:
        q._TASK_REGISTRY.pop("build_export_task", None)
    else:
        q._TASK_REGISTRY["build_export_task"] = prev
    get_settings.cache_clear()


@pytest.fixture
async def cleanup_export_jobs():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(ExportJob))
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=None))
        await s.commit()


@pytest.fixture
async def admin_with_known_password():
    """Reset the seeded admin's password to a known value for these tests."""
    new_pw = "danger-test-pw"
    async with AsyncSessionLocal() as s:
        acct = (await s.execute(select(Account).limit(1))).scalar_one()
        original_hash = acct.password_hash
        acct.password_hash = hash_password(new_pw)
        await s.commit()
    try:
        yield acct, new_pw
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(update(Account).where(Account.id == acct.id).values(password_hash=original_hash))
            await s.commit()


async def test_verify_password_ok(admin_with_known_password):
    admin, pw = admin_with_known_password
    async with AsyncSessionLocal() as s:
        # Should not raise.
        await danger.verify_password_or_raise(s, admin=admin, password=pw)


async def test_verify_password_wrong(admin_with_known_password):
    admin, _ = admin_with_known_password
    async with AsyncSessionLocal() as s:
        with pytest.raises(danger.DangerError):
            await danger.verify_password_or_raise(s, admin=admin, password="WRONG")


async def test_request_export_inserts_pending(admin_with_known_password, cleanup_export_jobs):
    admin, _ = admin_with_known_password
    async with AsyncSessionLocal() as s:
        job = await danger.request_export(s, admin=admin)
        await s.commit()
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(ExportJob))).scalars().all()
    assert len(rows) == 1
    assert rows[0].id == job.id
    assert rows[0].status == "pending"
    assert rows[0].requested_by == admin.email


async def test_schedule_site_deletion_sets_pending_at(cleanup_export_jobs):
    async with AsyncSessionLocal() as s:
        scheduled_at = await danger.schedule_site_deletion(s, days=7)
        await s.commit()
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is not None
    # Should be ~7 days from now.
    delta = sm.pending_delete_at - datetime.now(UTC)
    assert timedelta(days=6, hours=23) < delta <= timedelta(days=7, minutes=1)


async def test_schedule_site_deletion_when_already_scheduled(cleanup_export_jobs):
    async with AsyncSessionLocal() as s:
        await danger.schedule_site_deletion(s, days=7)
        await s.commit()
    async with AsyncSessionLocal() as s:
        with pytest.raises(danger.DangerError, match="already"):
            await danger.schedule_site_deletion(s, days=7)


async def test_cancel_site_deletion(cleanup_export_jobs):
    async with AsyncSessionLocal() as s:
        await danger.schedule_site_deletion(s, days=7)
        await s.commit()
    async with AsyncSessionLocal() as s:
        await danger.cancel_site_deletion(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is None


async def test_cancel_site_deletion_idempotent(cleanup_export_jobs):
    async with AsyncSessionLocal() as s:
        await danger.cancel_site_deletion(s)
        await s.commit()
    # No error.


async def test_get_danger_status_with_no_pending(cleanup_export_jobs):
    async with AsyncSessionLocal() as s:
        status = await danger.get_danger_status(s)
    assert status.pending_delete_at is None
    assert status.days_remaining is None


async def test_get_danger_status_with_pending(cleanup_export_jobs):
    async with AsyncSessionLocal() as s:
        await danger.schedule_site_deletion(s, days=7)
        await s.commit()
    async with AsyncSessionLocal() as s:
        status = await danger.get_danger_status(s)
    assert status.pending_delete_at is not None
    assert status.days_remaining in (6, 7)


async def test_list_exports_orders_desc(admin_with_known_password, cleanup_export_jobs):
    admin, _ = admin_with_known_password
    async with AsyncSessionLocal() as s:
        for _ in range(3):
            await danger.request_export(s, admin=admin)
        await s.commit()
    async with AsyncSessionLocal() as s:
        rows = await danger.list_exports(s, limit=10)
    assert len(rows) == 3
    # DESC ordering: created_at on row 0 should be >= row 2.
    assert rows[0].created_at >= rows[-1].created_at
