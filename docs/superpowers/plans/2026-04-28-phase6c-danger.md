# Phase 6c — Danger Zone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin-only catastrophic operations: async export to zip (manifest + posts/*.md + tables.json + media/) and 7-day-grace delete-site that wipes content but preserves admin login. Both require password re-auth.

**Architecture:** ARQ async pipeline mirrors P6b (one task per request → status polling → file download). 3 new ARQ tasks (`build_export_task` ad-hoc, `check_pending_site_deletion` hourly, `prune_old_exports` daily 03:30). New table `export_jobs`. New column `site_meta.pending_delete_at`. 7 admin endpoints; rate-limited 1/hour/IP.

**Tech Stack:** FastAPI 0.115+, async SQLAlchemy 2.0, Postgres 16, ARQ (existing), argon2 (existing for password verify), `zipfile` stdlib, Pydantic v2.

---

## File Map

**Create**
- `backend/alembic/versions/0007_danger.py`
- `backend/app/models/export_job.py`
- `backend/app/schemas/danger.py`
- `backend/app/services/danger.py`
- `backend/app/services/export_builder.py`
- `backend/app/services/site_wiper.py`
- `backend/app/workers/tasks/danger.py`
- `backend/app/routers/admin/danger.py`
- `backend/tests/test_danger_service.py`
- `backend/tests/test_export_builder.py`
- `backend/tests/test_site_wiper.py`
- `backend/tests/test_danger_tasks.py`
- `backend/tests/test_admin_danger.py`
- `backend/tests/test_alembic_0007_roundtrip.py`

**Modify**
- `backend/app/models/__init__.py` — register `ExportJob`
- `backend/app/models/site_meta.py` — add `pending_delete_at`
- `backend/app/workers/tasks/__init__.py` — re-export 3 new tasks
- `backend/app/workers/runner.py` — register tasks + cron entries
- `backend/app/routers/admin/__init__.py` — include `danger` router
- `backend/tests/conftest.py` — register 3 new tasks for inline mode

---

## Task 1: Migration 0007 + ORM models

**Files:**
- Create: `backend/alembic/versions/0007_danger.py`
- Create: `backend/app/models/export_job.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/site_meta.py`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/0007_danger.py`:

```python
"""danger

Revision ID: 0007_danger
Revises: 0006_analytics

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_danger"
down_revision: str | None = "0006_analytics"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_export_jobs_created_at",
        "export_jobs",
        [sa.text("created_at DESC")],
    )

    op.add_column(
        "site_meta",
        sa.Column("pending_delete_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("site_meta", "pending_delete_at")
    op.drop_index("ix_export_jobs_created_at", table_name="export_jobs")
    op.drop_table("export_jobs")
```

- [ ] **Step 2: Apply forward**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run alembic upgrade head
```

Expected: `Running upgrade 0006_analytics -> 0007_danger, danger`. No errors.

- [ ] **Step 3: Verify schema**

```bash
docker exec backend-postgres-1 psql -U myblog -d myblog -c "\d export_jobs" 2>&1 | head -15
docker exec backend-postgres-1 psql -U myblog -d myblog -c "\d site_meta" 2>&1 | grep pending_delete_at
```

Expected: `export_jobs` shows 7 columns (id varchar(36) PK, status, requested_by, file_size bigint, error text, created_at, completed_at). `site_meta` line shows `pending_delete_at | timestamp with time zone |`.

- [ ] **Step 4: Round-trip down/up**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run alembic downgrade 0006_analytics && uv run alembic upgrade head
```

Expected: clean down then up.

- [ ] **Step 5: Write ExportJob ORM**

Create `backend/app/models/export_job.py`:

```python
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

- [ ] **Step 6: Register ExportJob in models/__init__.py**

In `backend/app/models/__init__.py`, after `from app.models.event_log import EventLog`, add:

```python
from app.models.export_job import ExportJob
```

In `__all__`, add `"ExportJob",` (alphabetically between `"EventLog"` and `"HitDaily"`).

- [ ] **Step 7: Add pending_delete_at to SiteMeta**

In `backend/app/models/site_meta.py`, after the existing `avatar_id` column add:

```python
    pending_delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

Update the `from sqlalchemy import` line at the top of the file to include `DateTime`. If the existing import line is:

```python
from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
```

Replace with:

```python
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text
```

Also update the `from datetime` import — if currently `from datetime import date`, change to `from datetime import date, datetime`.

- [ ] **Step 8: Verify**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run python -c "from app.models import ExportJob, SiteMeta; print(ExportJob.__tablename__, [c.name for c in SiteMeta.__table__.columns if c.name == 'pending_delete_at'])"
```

Expected: `export_jobs ['pending_delete_at']`

- [ ] **Step 9: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add alembic/versions/0007_danger.py app/models/export_job.py app/models/__init__.py app/models/site_meta.py
git commit -m "feat(phase6c): 0007 migration + ORM (export_jobs + site_meta.pending_delete_at)"
```

---

## Task 2: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/danger.py`

- [ ] **Step 1: Write schemas**

Create `backend/app/schemas/danger.py`:

```python
"""Pydantic schemas for the danger zone admin API."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExportRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)


class ExportJobItem(BaseModel):
    id: str
    status: Literal["pending", "running", "done", "failed"]
    requested_by: str
    file_size: int | None = None
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class ExportRequestResponse(BaseModel):
    job_id: str
    status: Literal["pending"]


class DeleteSiteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=512)
    handle: str = Field(min_length=1, max_length=64)


class ScheduleDeleteResponse(BaseModel):
    scheduled_at: datetime
    days_remaining: int


class DangerStatusResponse(BaseModel):
    pending_delete_at: datetime | None = None
    days_remaining: int | None = None
```

- [ ] **Step 2: Verify**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run python -c "from app.schemas.danger import ExportRequest, ExportJobItem, ExportRequestResponse, DeleteSiteRequest, ScheduleDeleteResponse, DangerStatusResponse; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/schemas/danger.py
git commit -m "feat(phase6c): Pydantic schemas for danger zone"
```

---

## Task 3: danger service (TDD)

**Files:**
- Create: `backend/app/services/danger.py`
- Create: `backend/tests/test_danger_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_danger_service.py`:

```python
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
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_danger_service.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.danger'`.

- [ ] **Step 3: Implement service**

Create `backend/app/services/danger.py`:

```python
"""Danger zone service: password verification, export job lifecycle,
delete scheduling, status."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, ExportJob, SiteMeta
from app.schemas.danger import DangerStatusResponse
from app.services.auth import verify_password
from app.workers import queue as q


class DangerError(Exception):
    """Raised when a danger zone precondition fails (wrong password, already
    scheduled, etc.). Routers catch and translate to HTTP."""


async def verify_password_or_raise(
    s: AsyncSession, *, admin: Account, password: str
) -> None:
    if not verify_password(admin.password_hash, password):
        raise DangerError("invalid credentials")


async def request_export(s: AsyncSession, *, admin: Account) -> ExportJob:
    job = ExportJob(
        id=uuid.uuid4().hex,
        status="pending",
        requested_by=admin.email,
        created_at=datetime.now(UTC),
    )
    s.add(job)
    await s.flush()
    await s.refresh(job)
    await q.enqueue("build_export_task", job_id=job.id)
    return job


async def get_export(s: AsyncSession, *, job_id: str) -> ExportJob | None:
    return (
        await s.execute(select(ExportJob).where(ExportJob.id == job_id))
    ).scalar_one_or_none()


async def list_exports(
    s: AsyncSession, *, limit: int = 20
) -> list[ExportJob]:
    return list(
        (
            await s.execute(
                select(ExportJob).order_by(ExportJob.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def schedule_site_deletion(
    s: AsyncSession, *, days: int = 7
) -> datetime:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    if sm.pending_delete_at is not None:
        raise DangerError("delete already scheduled")
    when = datetime.now(UTC) + timedelta(days=days)
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=when)
    )
    await s.flush()
    return when


async def cancel_site_deletion(s: AsyncSession) -> None:
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=None)
    )
    await s.flush()


async def get_danger_status(s: AsyncSession) -> DangerStatusResponse:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    if sm.pending_delete_at is None:
        return DangerStatusResponse(pending_delete_at=None, days_remaining=None)
    remaining = sm.pending_delete_at - datetime.now(UTC)
    return DangerStatusResponse(
        pending_delete_at=sm.pending_delete_at,
        days_remaining=max(0, remaining.days),
    )
```

- [ ] **Step 4: Run — expect 10 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_danger_service.py -x 2>&1 | tail -10
```

Expected: `10 passed`.

Note: the `request_export` test calls `q.enqueue("build_export_task", ...)` which doesn't exist yet (Task 6). In `ARQ_INLINE` mode with the task unregistered, `enqueue` raises `RuntimeError("task 'build_export_task' not registered")`. Wrap the test fixture so we register a no-op for this test:

Add at the top of the test file (before the tests, after imports):

```python
@pytest.fixture(autouse=True)
def _register_noop_export_task():
    """Stub the build_export_task in inline-mode registry so danger
    service tests don't depend on the task implementation."""
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
```

After adding this fixture, re-run pytest. Expect `10 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/danger.py tests/test_danger_service.py
git commit -m "feat(phase6c): danger service (verify_password + export lifecycle + schedule)"
```

---

## Task 4: site_wiper service (TDD)

**Files:**
- Create: `backend/app/services/site_wiper.py`
- Create: `backend/tests/test_site_wiper.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_site_wiper.py`:

```python
"""site_wiper service unit tests."""
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO

import pytest
from PIL import Image
from sqlalchemy import delete, func, select, update

from app.db import AsyncSessionLocal
from app.models import (
    Account,
    Comment,
    Contact,
    ContribDay,
    EventLog,
    HitDaily,
    HitEvent,
    Integration,
    LikeEvent,
    Media,
    NowEntry,
    Post,
    Project,
    SiteMeta,
    Tag,
)
from app.services import site_wiper


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def seeded_site(tmp_path, monkeypatch):
    """Seed a few rows into every wipe-target table + a media file on disk.
    Yields the tmp_path used as MEDIA_DIR."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)

    # Seed minimal rows. We rely on the existing CLI bootstrap so admin and
    # site_meta already exist.
    async with AsyncSessionLocal() as s:
        # Get an existing tag so we can FK posts to it.
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        # post
        s.add(Post(
            id="wipetest", n="9", title="W", subtitle="", date=datetime.now(UTC).date(),
            read="1", lang="en", summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=tag.id,
        ))
        # contact
        s.add(Contact(label="x", value="x@x.com", href="mailto:x@x.com",
                      visible=True, sort_order=0))
        # now entry
        s.add(NowEntry(body_md="hi", listening="", reading="",
                       is_current=True, created_at=datetime.now(UTC)))
        # contrib_day
        s.add(ContribDay(date=datetime.now(UTC).date(), count=3))
        # like
        s.add(LikeEvent(post_id="wipetest", ip_hash="abc",
                        day=datetime.now(UTC).date(), created_at=datetime.now(UTC)))
        # hit
        s.add(HitEvent(path="/", created_at=datetime.now(UTC)))
        s.add(HitDaily(date=datetime.now(UTC).date(), path="/",
                       hits=3, referrers_top=[], countries_top=[]))
        # integration
        s.add(Integration(provider="github", access_token_encrypted="x",
                          extra_json={}))
        # media file on disk + DB row
        bucket_dir = tmp_path / "aa"
        bucket_dir.mkdir(parents=True, exist_ok=True)
        png = BytesIO()
        Image.new("RGB", (4, 4), "green").save(png, format="PNG")
        media_path = bucket_dir / "wipetest-cat.png"
        media_path.write_bytes(png.getvalue())
        s.add(Media(
            filename="cat.png", storage_path="aa/wipetest-cat.png",
            mime_type="image/png", size=len(png.getvalue()),
            width=4, height=4, alt=None, created_at=datetime.now(UTC),
        ))
        # event_log noise
        s.add(EventLog(type="test.seed", actor="test", target=None, meta={}))
        await s.commit()

    yield tmp_path

    # Re-bootstrap is heavy; tests run wipe and verify, then we re-seed
    # via cli or just leave the empty state. Cleanup just removes leftover
    # rows (idempotent).


async def test_wipe_clears_content_tables(seeded_site):
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()

    async with AsyncSessionLocal() as s:
        for model in (Post, Contact, NowEntry, ContribDay, LikeEvent,
                      HitEvent, HitDaily, Integration, Media, Comment, Tag, Project):
            count = (await s.execute(select(func.count()).select_from(model))).scalar()
            assert count == 0, f"{model.__name__} not wiped: {count} rows"


async def test_wipe_preserves_admin(seeded_site):
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(Account))).scalars().all()
        before_count = len(before)
        before_email = before[0].email if before else None
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        after = (await s.execute(select(Account))).scalars().all()
    assert len(after) == before_count
    assert after[0].email == before_email


async def test_wipe_resets_site_meta_to_defaults(seeded_site):
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(
            handle="custom", name="Custom", pending_delete_at=datetime.now(UTC)
        ))
        await s.commit()
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.handle == "wangyang"
    assert sm.name == "汪洋"
    assert sm.pending_delete_at is None
    assert sm.avatar_id is None


async def test_wipe_preserves_event_log(seeded_site):
    async with AsyncSessionLocal() as s:
        before = (await s.execute(select(func.count()).select_from(EventLog))).scalar()
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    async with AsyncSessionLocal() as s:
        after = (await s.execute(select(func.count()).select_from(EventLog))).scalar()
    assert after >= before  # event_log preserved (and may have new rows from the wipe itself)


async def test_wipe_removes_media_files_on_disk(seeded_site):
    media_dir = seeded_site
    f = media_dir / "aa" / "wipetest-cat.png"
    assert f.exists()
    async with AsyncSessionLocal() as s:
        await site_wiper.wipe_site_content(s)
        await s.commit()
    assert not f.exists()
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_site_wiper.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.site_wiper'`.

- [ ] **Step 3: Implement service**

Create `backend/app/services/site_wiper.py`:

```python
"""Site content wipe service: TRUNCATE content tables, reset site_meta to
CLI seed defaults, unlink media files. Preserves admin login + audit trail."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Comment,
    Contact,
    ContribDay,
    HitDaily,
    HitEvent,
    Integration,
    LikeEvent,
    Media,
    NowEntry,
    Post,
    Project,
    SiteMeta,
    Tag,
)
from app.services import media_storage


# Order matters: child tables before their parents to satisfy FK constraints.
# Posts has FK to tags → wipe Posts before Tags.
# Comments / Likes have FK to posts → wipe before posts.
# HitEvents / HitDaily have FK to posts → wipe before posts.
# Media has no inbound FK from content; site_meta.avatar_id is NULL'd via
#   ON DELETE SET NULL when we wipe Media.
WIPE_ORDER = [
    HitEvent, HitDaily, LikeEvent, Comment,
    Post, Tag,                   # Post → Tag FK
    Project, Contact, NowEntry, ContribDay,
    Integration,
    Media,                       # ON DELETE SET NULL fires for site_meta.avatar_id
]


SITE_META_DEFAULTS = {
    "handle": "wangyang",
    "name": "汪洋",
    "name_en": "Wang Yang",
    "role": "Backend / AI Full-Stack Engineer",
    "tagline": "Backends that don't flinch. Models that ship.",
    "bio": "I build backend systems and AI agents.",
    "location": "Hangzhou, CN",
    "email": "hi@wangyang.dev",
    "github": "wangyang",
    "pronouns": None,
    "avatar_path": None,
    "avatar_id": None,
    "typing_line": (
        "// building backends that don't flinch.\n// training models that ship."
    ),
    "stack_chips": ["Java", "Python", "PyTorch", "Agents", "Segmentation"],
    "footer_note": "© 2026 Wang Yang · hand-coded · cookie-less analytics",
    "default_theme": "dark",
    "accent_color": "oklch(82% 0.17 152)",
    "accent2_color": "oklch(80% 0.15 70)",
    "violet_color": "oklch(72% 0.18 295)",
    "danger_color": "oklch(70% 0.2 25)",
    "launched_at": date(2023, 1, 1),
    "pet_config": {},
    "pending_delete_at": None,
}


async def wipe_site_content(s: AsyncSession) -> dict:
    """TRUNCATE content tables + reset site_meta to defaults + unlink media files.
    Returns {tables_wiped, rows_destroyed_total}.

    Order of operations:
      1. Walk Media rows: unlink each file under data/media/ (idempotent if missing).
      2. DELETE all WIPE_ORDER tables in FK-safe order.
      3. UPDATE site_meta SET ... = defaults WHERE id = 1.
    """
    # Step 1: unlink media files first.
    media_rows = (await s.execute(select(Media))).scalars().all()
    for m in media_rows:
        try:
            await media_storage.delete(m.storage_path)
        except Exception:
            pass  # idempotent — missing files are fine

    # Step 2: TRUNCATE content tables.
    rows_destroyed = 0
    tables_wiped = 0
    for model in WIPE_ORDER:
        res = await s.execute(delete(model))
        rows_destroyed += res.rowcount or 0
        tables_wiped += 1

    # Step 3: reset site_meta to defaults.
    await s.execute(
        update(SiteMeta).where(SiteMeta.id == 1).values(**SITE_META_DEFAULTS)
    )
    await s.flush()
    return {"tables_wiped": tables_wiped, "rows_destroyed_total": rows_destroyed}
```

- [ ] **Step 4: Run — expect 5 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_site_wiper.py -x 2>&1 | tail -10
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/site_wiper.py tests/test_site_wiper.py
git commit -m "feat(phase6c): site_wiper (TRUNCATE content + reset site_meta + unlink media)"
```

---

## Task 5: export_builder service (TDD)

**Files:**
- Create: `backend/app/services/export_builder.py`
- Create: `backend/tests/test_export_builder.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_export_builder.py`:

```python
"""export_builder service unit tests."""
from __future__ import annotations

import json
import zipfile
from datetime import UTC, datetime
from io import BytesIO

import pytest
import yaml
from PIL import Image
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import (
    Account,
    ExportJob,
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
```

- [ ] **Step 2: Add yaml dep**

Pillow + PyYAML are already available (yaml ships with the python install via pyyaml — verify):

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run python -c "import yaml; print(yaml.__version__)"
```

If this fails (`ModuleNotFoundError`), add `"pyyaml>=6",` to `pyproject.toml` `dependencies`, run `uv sync --all-extras`, and re-verify.

- [ ] **Step 3: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_export_builder.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.export_builder'`.

- [ ] **Step 4: Implement service**

Create `backend/app/services/export_builder.py`:

```python
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
    """Serialize a SQLAlchemy row to a JSON-safe dict (datetimes → ISO,
    dates → ISO, JSONB stays as-is)."""
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
                # tag_id → tag_slug map for post frontmatter resolution.
                tags = (await s.execute(select(Tag))).scalars().all()
                tag_id_to_slug = {t.id: t.slug for t in tags}

                # Posts → individual md files
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

                # Other tables → tables.json
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
            media_dir = get_settings().data_dir / "media"
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
```

- [ ] **Step 5: Run — expect 6 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_export_builder.py -x 2>&1 | tail -10
```

Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/export_builder.py tests/test_export_builder.py
git commit -m "feat(phase6c): export_builder (manifest + posts md + tables.json + media)"
```

---

## Task 6: ARQ build_export_task

**Files:**
- Create: `backend/app/workers/tasks/danger.py`
- Modify: `backend/app/workers/tasks/__init__.py`
- Modify: `backend/app/workers/runner.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_danger_tasks.py` (initial subset)

- [ ] **Step 1: Write failing tests for build_export_task**

Create `backend/tests/test_danger_tasks.py`:

```python
"""ARQ danger tasks unit tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select, update

from app.db import AsyncSessionLocal
from app.models import ExportJob, SiteMeta
from app.workers.tasks.danger import build_export_task


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
async def export_dir(tmp_path, monkeypatch):
    from app.services import export_builder
    monkeypatch.setattr(export_builder, "_exports_dir", lambda: tmp_path)
    return tmp_path


async def test_build_export_task_happy_path(cleanup_jobs, export_dir):
    job_id = "btest-ok"
    async with AsyncSessionLocal() as s:
        s.add(ExportJob(
            id=job_id, status="pending", requested_by="x@x.com",
            created_at=datetime.now(UTC),
        ))
        await s.commit()

    res = await build_export_task({}, job_id=job_id)
    assert res["status"] == "done"
    assert res["file_size"] > 0

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(ExportJob).where(ExportJob.id == job_id))).scalar_one()
    assert row.status == "done"
    assert row.file_size > 0
    assert row.completed_at is not None
    assert (export_dir / f"{job_id}.zip").exists()


async def test_build_export_task_failure_path(cleanup_jobs, export_dir, monkeypatch):
    job_id = "btest-fail"
    async with AsyncSessionLocal() as s:
        s.add(ExportJob(
            id=job_id, status="pending", requested_by="x@x.com",
            created_at=datetime.now(UTC),
        ))
        await s.commit()

    from app.services import export_builder
    async def _boom(jid):
        raise RuntimeError("simulated failure")
    monkeypatch.setattr(export_builder, "build_export_zip", _boom)

    with pytest.raises(RuntimeError, match="simulated"):
        await build_export_task({}, job_id=job_id)

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(ExportJob).where(ExportJob.id == job_id))).scalar_one()
    assert row.status == "failed"
    assert row.error and "simulated" in row.error
    assert row.completed_at is not None
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_danger_tasks.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.workers.tasks.danger'`.

- [ ] **Step 3: Implement task**

Create `backend/app/workers/tasks/danger.py`:

```python
"""ARQ tasks for the danger zone: export building, scheduled-deletion check,
and old-export pruning."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select, update

from app.config import get_settings
from app.db import AsyncSessionLocal
from app.models import ExportJob, SiteMeta
from app.services import export_builder
from app.services.event_log import write_event
from app.services.site_wiper import wipe_site_content


async def build_export_task(ctx: dict, job_id: str) -> dict:
    """Drive a single export job: pending → running → done|failed."""
    # Step 1: pending → running
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(ExportJob).where(ExportJob.id == job_id).values(status="running")
        )
        await s.commit()

    try:
        path, size = await export_builder.build_export_zip(job_id)
    except Exception as e:
        async with AsyncSessionLocal() as s:
            await s.execute(
                update(ExportJob).where(ExportJob.id == job_id).values(
                    status="failed",
                    error=f"{type(e).__name__}: {e}",
                    completed_at=datetime.now(UTC),
                )
            )
            await write_event(
                s, type="danger.export_failed", actor="system",
                target=job_id, meta={"error": str(e)},
            )
            await s.commit()
        raise

    async with AsyncSessionLocal() as s:
        await s.execute(
            update(ExportJob).where(ExportJob.id == job_id).values(
                status="done",
                file_size=size,
                completed_at=datetime.now(UTC),
            )
        )
        await write_event(
            s, type="danger.export_completed", actor="system",
            target=job_id, meta={"file_size": size},
        )
        await s.commit()

    return {"status": "done", "job_id": job_id, "file_size": size}


async def check_pending_site_deletion(ctx: dict) -> dict:
    """Hourly cron: trigger wipe when site_meta.pending_delete_at <= NOW()."""
    fired = 0
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
        if sm.pending_delete_at is not None and sm.pending_delete_at <= datetime.now(UTC):
            stats = await wipe_site_content(s)
            await write_event(
                s, type="danger.site_wiped", actor="system",
                target=None, meta=stats,
            )
            await s.commit()
            fired = 1
    return {"checked": 1, "fired": fired}


async def prune_old_exports(ctx: dict) -> dict:
    """Daily 03:30: remove zips and rows older than 7 days."""
    cutoff = datetime.now(UTC) - timedelta(days=7)
    exports_dir = get_settings().data_dir / "exports"
    files_deleted = 0

    if exports_dir.exists():
        for f in exports_dir.iterdir():
            if f.is_file() and f.suffix == ".zip":
                mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
                if mtime < cutoff:
                    f.unlink(missing_ok=True)
                    files_deleted += 1

    async with AsyncSessionLocal() as s:
        res = await s.execute(
            delete(ExportJob).where(ExportJob.created_at < cutoff)
        )
        rows_deleted = res.rowcount or 0
        await s.commit()

    return {"files_deleted": files_deleted, "rows_deleted": rows_deleted}
```

- [ ] **Step 4: Re-export in tasks/__init__.py**

In `backend/app/workers/tasks/__init__.py`, after `from app.workers.tasks.analytics import analytics_rollup`, add:

```python
from app.workers.tasks.danger import (
    build_export_task,
    check_pending_site_deletion,
    prune_old_exports,
)
```

In `__all__`, add the three names alphabetically:

```python
__all__ = [
    "analytics_rollup",
    "build_export_task",
    "check_pending_site_deletion",
    "cleanup_expired_magic_links",
    "prune_event_log",
    "prune_old_exports",
    "publish_scheduled_posts",
    "recompute_post_word_counts",
    "send_email_task",
    "sync_github_contrib",
]
```

- [ ] **Step 5: Register in runner.py**

In `backend/app/workers/runner.py`, after `q.register("analytics_rollup", t.analytics_rollup)` add:

```python
q.register("build_export_task", t.build_export_task)
q.register("check_pending_site_deletion", t.check_pending_site_deletion)
q.register("prune_old_exports", t.prune_old_exports)
```

In `WorkerSettings.functions`, append the three new tasks (matching the existing list shape).

In `WorkerSettings.cron_jobs`, append:

```python
        cron(t.check_pending_site_deletion, minute={0}),         # hourly :00
        cron(t.prune_old_exports, hour={3}, minute={30}),        # daily 03:30 UTC
```

- [ ] **Step 6: Register in test conftest**

In `backend/tests/conftest.py`'s `_register_arq_tasks` fixture, add three lines after the existing `q.register("analytics_rollup", ...)`:

```python
    q.register("build_export_task", t.build_export_task)
    q.register("check_pending_site_deletion", t.check_pending_site_deletion)
    q.register("prune_old_exports", t.prune_old_exports)
```

- [ ] **Step 7: Update `test_workers_runner.py` expected set**

In `backend/tests/test_workers_runner.py`, the existing `test_all_seven_tasks_listed_in_functions` expects 7 tasks. Now there are 10. Rename to `test_all_ten_tasks_listed_in_functions` and add the three new task names:

```python
def test_all_ten_tasks_listed_in_functions():
    names = {f.__name__ for f in WorkerSettings.functions}
    assert names == {
        "send_email_task",
        "publish_scheduled_posts",
        "cleanup_expired_magic_links",
        "prune_event_log",
        "recompute_post_word_counts",
        "sync_github_contrib",
        "analytics_rollup",
        "build_export_task",
        "check_pending_site_deletion",
        "prune_old_exports",
    }
```

- [ ] **Step 8: Run — expect 2 PASS for the new task tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_danger_tasks.py tests/test_workers_runner.py -x 2>&1 | tail -10
```

Expected: 5 passed (2 danger task tests + 3 workers runner tests).

- [ ] **Step 9: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/workers/tasks/danger.py app/workers/tasks/__init__.py app/workers/runner.py tests/conftest.py tests/test_workers_runner.py tests/test_danger_tasks.py
git commit -m "feat(phase6c): build_export_task ARQ task + cron registrations"
```

---

## Task 7: ARQ check_pending_site_deletion + prune_old_exports tests

**Files:**
- Modify: `backend/tests/test_danger_tasks.py`

The implementation already lives in `app/workers/tasks/danger.py` from task 6. Add tests for the other two task functions.

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_danger_tasks.py`:

```python
async def test_check_pending_no_schedule_is_noop(cleanup_jobs):
    from app.workers.tasks.danger import check_pending_site_deletion
    res = await check_pending_site_deletion({})
    assert res == {"checked": 1, "fired": 0}


async def test_check_pending_in_past_fires_wipe(cleanup_jobs, tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)
    from app.workers.tasks.danger import check_pending_site_deletion

    past = datetime.now(UTC) - timedelta(hours=1)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pending_delete_at=past))
        await s.commit()

    res = await check_pending_site_deletion({})
    assert res == {"checked": 1, "fired": 1}

    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is None


async def test_prune_old_exports_deletes_aged_files_and_rows(cleanup_jobs, tmp_path, monkeypatch):
    """Seed an old zip + a recent zip + corresponding rows; verify pruning."""
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    old_zip = exports_dir / "old.zip"
    old_zip.write_bytes(b"PK\x03\x04 stub")
    # Set mtime to 8 days ago.
    import os
    eight_days_ago = (datetime.now(UTC) - timedelta(days=8)).timestamp()
    os.utime(old_zip, (eight_days_ago, eight_days_ago))

    new_zip = exports_dir / "new.zip"
    new_zip.write_bytes(b"PK\x03\x04 stub")  # mtime ≈ now

    async with AsyncSessionLocal() as s2:
        s2.add(ExportJob(id="old", status="done", requested_by="x@x.com",
                         created_at=datetime.now(UTC) - timedelta(days=8)))
        s2.add(ExportJob(id="new", status="done", requested_by="x@x.com",
                         created_at=datetime.now(UTC)))
        await s2.commit()

    from app.workers.tasks.danger import prune_old_exports
    res = await prune_old_exports({})
    assert res["files_deleted"] >= 1
    assert res["rows_deleted"] >= 1

    assert not old_zip.exists()
    assert new_zip.exists()

    async with AsyncSessionLocal() as s3:
        rows = (await s3.execute(select(ExportJob))).scalars().all()
    assert {r.id for r in rows} == {"new"}


async def test_prune_old_exports_no_op_when_nothing_old(cleanup_jobs, tmp_path, monkeypatch):
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "data_dir", tmp_path)

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    from app.workers.tasks.danger import prune_old_exports
    res = await prune_old_exports({})
    assert res == {"files_deleted": 0, "rows_deleted": 0}
```

- [ ] **Step 2: Run — expect 6 PASS** (2 from task 6 + 4 new)

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_danger_tasks.py -x 2>&1 | tail -10
```

Expected: `6 passed`.

- [ ] **Step 3: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add tests/test_danger_tasks.py
git commit -m "test(phase6c): check_pending_site_deletion + prune_old_exports coverage"
```

---

## Task 8: Admin router — POST /export, GET /export/{id}, GET /exports

**Files:**
- Create: `backend/app/routers/admin/danger.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Create: `backend/tests/test_admin_danger.py`

- [ ] **Step 1: Write failing tests (subset for these 3 endpoints)**

Create `backend/tests/test_admin_danger.py`:

```python
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
```

- [ ] **Step 2: Run — expect 404/failure (route not registered)**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_danger.py -x 2>&1 | tail -10
```

Expected: failures.

- [ ] **Step 3: Write the router (skeleton + 3 endpoints)**

Create `backend/app/routers/admin/danger.py`:

```python
"""Admin danger zone: site export + delete-site (with 7-day grace)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, ExportJob
from app.redis import get_redis
from app.schemas.danger import (
    ExportJobItem,
    ExportRequest,
    ExportRequestResponse,
)
from app.services import danger as danger_svc
from app.services import rate_limit
from app.services.client_ip import client_ip_key_part
from app.services.event_log import write_event

router = APIRouter()


def _to_export_item(row: ExportJob) -> ExportJobItem:
    return ExportJobItem(
        id=row.id,
        status=row.status,
        requested_by=row.requested_by,
        file_size=row.file_size,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


async def _danger_rate_limit(request: Request, redis) -> None:
    ip_key = client_ip_key_part(request)
    await rate_limit.hit(redis, f"rl:danger:{ip_key}", limit=1, window_sec=3600)


@router.post(
    "/danger/export",
    response_model=ExportRequestResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def request_export_route(
    req: ExportRequest,
    request: Request,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> ExportRequestResponse:
    await _danger_rate_limit(request, redis)
    try:
        await danger_svc.verify_password_or_raise(s, admin=admin, password=req.password)
    except danger_svc.DangerError:
        raise HTTPException(401, "invalid credentials")

    job = await danger_svc.request_export(s, admin=admin)
    await write_event(
        s, type="danger.export_requested", actor=admin.email,
        target=job.id, meta={},
    )
    await s.commit()
    return ExportRequestResponse(job_id=job.id, status="pending")


@router.get(
    "/danger/export/{job_id}",
    response_model=ExportJobItem,
)
async def get_export_route(
    job_id: str,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> ExportJobItem:
    row = await danger_svc.get_export(s, job_id=job_id)
    if row is None:
        raise HTTPException(404, "export not found")
    return _to_export_item(row)


@router.get(
    "/danger/exports",
    response_model=list[ExportJobItem],
)
async def list_exports_route(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ExportJobItem]:
    rows = await danger_svc.list_exports(s, limit=20)
    return [_to_export_item(r) for r in rows]
```

- [ ] **Step 4: Register router**

In `backend/app/routers/admin/__init__.py`, add the import (alphabetical):

```python
from app.routers.admin.danger import router as danger_router
```

And below:

```python
router.include_router(danger_router, tags=["admin·danger"])
```

- [ ] **Step 5: Run — expect 5 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_danger.py -x 2>&1 | tail -10
```

Expected: `5 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/admin/danger.py app/routers/admin/__init__.py tests/test_admin_danger.py
git commit -m "feat(phase6c): POST /admin/danger/export + GET /export/:id + /exports"
```

---

## Task 9: Admin router — GET /export/{id}/download

**Files:**
- Modify: `backend/app/routers/admin/danger.py`
- Modify: `backend/tests/test_admin_danger.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_admin_danger.py`:

```python
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
```

- [ ] **Step 2: Run — expect 404 / route missing**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_danger.py -k download -x 2>&1 | tail -10
```

Expected: failures.

- [ ] **Step 3: Add download endpoint**

In `backend/app/routers/admin/danger.py`, update imports — add:

```python
from fastapi.responses import FileResponse

from app.config import get_settings
```

Append at the bottom:

```python
@router.get("/danger/export/{job_id}/download")
async def download_export_route(
    job_id: str,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
):
    row = await danger_svc.get_export(s, job_id=job_id)
    if row is None or row.status != "done":
        raise HTTPException(404, "export not ready")

    exports_dir = (get_settings().data_dir / "exports").resolve()
    candidate = (exports_dir / f"{job_id}.zip").resolve()

    # Path safety: candidate must live inside exports_dir.
    if exports_dir not in candidate.parents and candidate != exports_dir:
        raise HTTPException(404, "export not ready")
    if not candidate.exists():
        raise HTTPException(404, "export file missing on disk")

    return FileResponse(
        path=str(candidate),
        media_type="application/zip",
        filename=f"myblog-export-{job_id}.zip",
    )
```

- [ ] **Step 4: Run — expect 9 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_danger.py -x 2>&1 | tail -10
```

Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/admin/danger.py tests/test_admin_danger.py
git commit -m "feat(phase6c): GET /admin/danger/export/:id/download (FileResponse + traversal guard)"
```

---

## Task 10: Admin router — POST /delete-site + cancel + GET /status

**Files:**
- Modify: `backend/app/routers/admin/danger.py`
- Modify: `backend/tests/test_admin_danger.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_admin_danger.py`:

```python
HANDLE = "wangyang"


async def test_delete_site_unauthenticated_401(client, cleanup_jobs):
    r = await client.post("/api/admin/danger/delete-site",
                          json={"password": "x", "handle": HANDLE})
    assert r.status_code == 401


async def test_delete_site_wrong_password(client, admin_token, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/delete-site",
        json={"password": "WRONG", "handle": HANDLE},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 401
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is None


async def test_delete_site_wrong_handle(client, admin_token, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/delete-site",
        json={"password": KNOWN_PW, "handle": "WRONG-HANDLE"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_delete_site_correct_schedules(client, admin_token, cleanup_jobs):
    r = await client.post(
        "/api/admin/danger/delete-site",
        json={"password": KNOWN_PW, "handle": HANDLE},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["days_remaining"] == 7
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is not None


async def test_delete_site_already_scheduled_423(client, admin_token, cleanup_jobs):
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(
            pending_delete_at=datetime.now(UTC) + __import__('datetime').timedelta(days=7)
        ))
        await s.commit()
    r = await client.post(
        "/api/admin/danger/delete-site",
        json={"password": KNOWN_PW, "handle": HANDLE},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 423


async def test_delete_site_cancel_204(client, admin_token, cleanup_jobs):
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(
            pending_delete_at=datetime.now(UTC) + __import__('datetime').timedelta(days=7)
        ))
        await s.commit()
    r = await client.post(
        "/api/admin/danger/delete-site/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    assert sm.pending_delete_at is None


async def test_status_no_pending(client, admin_token, cleanup_jobs):
    r = await client.get(
        "/api/admin/danger/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["pending_delete_at"] is None
    assert body["days_remaining"] is None


async def test_status_with_pending(client, admin_token, cleanup_jobs):
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(
            pending_delete_at=datetime.now(UTC) + __import__('datetime').timedelta(days=7)
        ))
        await s.commit()
    r = await client.get(
        "/api/admin/danger/status",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = r.json()
    assert body["pending_delete_at"] is not None
    assert body["days_remaining"] in (6, 7)


async def test_rate_limit_429_after_first_call(client, admin_token, cleanup_jobs, export_dir):
    """Two POSTs to /danger/* within an hour from the same IP → second is 429."""
    r1 = await client.post(
        "/api/admin/danger/export",
        json={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 200
    r2 = await client.post(
        "/api/admin/danger/export",
        json={"password": KNOWN_PW},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 429
```

- [ ] **Step 2: Run — expect 404/failure**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_danger.py -k "delete or status or rate_limit" -x 2>&1 | tail -10
```

Expected: failures.

- [ ] **Step 3: Add 3 endpoints**

In `backend/app/routers/admin/danger.py`, add to imports:

```python
from fastapi import Response

from app.models import SiteMeta
from app.schemas.danger import (
    DangerStatusResponse,
    DeleteSiteRequest,
    ExportJobItem,
    ExportRequest,
    ExportRequestResponse,
    ScheduleDeleteResponse,
)
from sqlalchemy import select
```

(Adjust the existing schemas import line to include the new names if it's already partial.)

Append at the bottom:

```python
@router.post(
    "/danger/delete-site",
    response_model=ScheduleDeleteResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def delete_site_route(
    req: DeleteSiteRequest,
    request: Request,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> ScheduleDeleteResponse:
    await _danger_rate_limit(request, redis)
    try:
        await danger_svc.verify_password_or_raise(s, admin=admin, password=req.password)
    except danger_svc.DangerError:
        raise HTTPException(401, "invalid credentials")

    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    if req.handle != sm.handle:
        raise HTTPException(422, "handle mismatch")

    try:
        scheduled_at = await danger_svc.schedule_site_deletion(s, days=7)
    except danger_svc.DangerError:
        raise HTTPException(423, "delete already scheduled")

    await write_event(
        s, type="danger.delete_scheduled", actor=admin.email,
        target=None, meta={"scheduled_at": scheduled_at.isoformat()},
    )
    await s.commit()
    return ScheduleDeleteResponse(scheduled_at=scheduled_at, days_remaining=7)


@router.post(
    "/danger/delete-site/cancel",
    status_code=204,
    dependencies=[Depends(require_scope("write"))],
)
async def cancel_delete_site_route(
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    await danger_svc.cancel_site_deletion(s)
    await write_event(
        s, type="danger.delete_canceled", actor=admin.email,
        target=None, meta={},
    )
    await s.commit()
    return Response(status_code=204)


@router.get(
    "/danger/status",
    response_model=DangerStatusResponse,
)
async def get_danger_status_route(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DangerStatusResponse:
    return await danger_svc.get_danger_status(s)
```

- [ ] **Step 4: Run — expect 18 PASS** (9 prior + 9 new)

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_danger.py -x 2>&1 | tail -10
```

Expected: `18 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/admin/danger.py tests/test_admin_danger.py
git commit -m "feat(phase6c): POST /admin/danger/delete-site + cancel + GET /status"
```

---

## Task 11: Migration round-trip test

**Files:**
- Create: `backend/tests/test_alembic_0007_roundtrip.py`

- [ ] **Step 1: Write test**

Create `backend/tests/test_alembic_0007_roundtrip.py`:

```python
"""Round-trip alembic to 0006 and back to 0007."""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_0007_downgrade_then_upgrade_clean():
    down = _alembic("downgrade", "0006_analytics")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0006_analytics" in cur.stdout

    up = _alembic("upgrade", "0007_danger")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0007_danger" in cur.stdout

    # Restore head so other tests run against the latest schema.
    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
```

- [ ] **Step 2: Run**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_alembic_0007_roundtrip.py -v 2>&1 | tail -10
```

Expected: `1 passed`.

- [ ] **Step 3: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add tests/test_alembic_0007_roundtrip.py
git commit -m "test(phase6c): alembic 0007 round-trip"
```

---

## Task 12: Update prior alembic round-trip tests for 0007 head

**Files:**
- Modify: `backend/tests/test_alembic_0006_roundtrip.py`

- [ ] **Step 1: Read current 0006 round-trip**

```bash
cat /Users/sd3/Desktop/project/MyBlog/backend/tests/test_alembic_0006_roundtrip.py
```

The existing test asserts `0006_analytics` matches head. Now that 0007 is head, we need the same head-relative pattern as 0004/0005 round-trips: step explicitly to 0006 then restore head.

- [ ] **Step 2: Edit**

If the existing test ends with `assert "0006_analytics" in cur.stdout`, replace the body with:

```python
def test_0006_downgrade_then_upgrade_clean():
    down = _alembic("downgrade", "0005_media")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0005_media" in cur.stdout

    up = _alembic("upgrade", "0006_analytics")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0006_analytics" in cur.stdout

    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
```

(If it already steps explicitly per the P6b plan, this is a no-op confirmation.)

- [ ] **Step 3: Verify both round-trips pass**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_alembic_0004_roundtrip.py tests/test_alembic_0005_roundtrip.py tests/test_alembic_0006_roundtrip.py tests/test_alembic_0007_roundtrip.py -v 2>&1 | tail -8
```

Expected: 4 passed.

- [ ] **Step 4: Commit (only if file changed)**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git status -s tests/test_alembic_0006_roundtrip.py
# If modified:
git add tests/test_alembic_0006_roundtrip.py
git commit -m "test(phase6c): harden 0006 round-trip vs 0007 head drift"
# If clean: skip commit
```

---

## Task 13: Final full-suite + ruff verification

**Files:**
- (No new files)

- [ ] **Step 1: Full test suite**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest 2>&1 | tail -3
```

Expected: at least ~377 tests passing (P6b 346 baseline + ~31 new from P6c).

- [ ] **Step 2: ruff**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run ruff check . 2>&1 | tail -5
```

Expected: 8 errors (P3/P4 baseline only).

- [ ] **Step 3: Final report**

If any P6c-introduced ruff errors appear, list them. If full suite shows < 377, report the deficit.

If everything green, no commit needed.

---

## Acceptance Criteria Mapping

| Spec §10.6 criterion | Task |
|---|---|
| `export_jobs` table + `site_meta.pending_delete_at` column; round-trip clean | 1, 11 |
| `POST /danger/export` requires password; produces downloadable zip via ARQ | 8, 9 |
| Export zip layout matches spec (manifest + tables.json + posts/ + media/) | 5 |
| `POST /danger/delete-site` requires password AND handle literal match | 10 |
| `pending_delete_at` reads back via `GET /danger/status` | 10 |
| ARQ `check_pending_site_deletion` triggers wipe at the right time | 7 |
| `wipe_site_content` clears content but preserves accounts + event_log | 4 |
| `prune_old_exports` cleans aged zips + rows | 7 |
| 6 event_log types fire on the corresponding actions | 8, 10 (4 types) + 6 (2 types completed/failed) |
| All P3/P4/P5/P6a/P6b tests still pass | 13 |
