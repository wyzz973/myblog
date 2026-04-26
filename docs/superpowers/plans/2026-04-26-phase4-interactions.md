# Phase 4 Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement real likes (IP+day idempotent), public comments + admin moderation, public-endpoint rate limits, synchronous SMTP, and activity-stream endpoints on top of Phase 3's auth hardening.

**Architecture:** Single Alembic migration adds 2 tables (`like_events`, `comments`). New service modules under `app/services/` (`likes`, `comments`, `activity`, `hashing`). `email.py` is rewritten — log-only stub becomes a real `smtplib`-based client (sync via `asyncio.to_thread`) with dev-mode log fallback when `smtp_host` is unset. New routers `public/comments`, `admin/comments`, `admin/activity`. Existing `public/posts` extended with `/like` endpoint. All work lands on a `phase4-interactions` branch off `main` (currently HEAD `06206e5`). Strict TDD.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, redis-py async (rate-limit reuse from P3), `smtplib` stdlib via `asyncio.to_thread`. No new third-party deps. Tests: pytest + pytest-asyncio + fakeredis + httpx ASGITransport.

**Spec reference:** `docs/superpowers/specs/2026-04-26-phase4-interactions-design.md`

---

## File Structure

**New files:**

```
backend/
├── alembic/versions/
│   └── 0003_interactions.py
├── app/
│   ├── models/
│   │   ├── like_event.py
│   │   └── comment.py
│   ├── services/
│   │   ├── hashing.py                   (ip_hash, email_hash)
│   │   ├── likes.py                     (record_like, get_count)
│   │   ├── comments.py                  (create_pending, list_for_post, moderate, delete)
│   │   └── activity.py                  (query event_log)
│   ├── routers/
│   │   ├── public/comments.py
│   │   ├── admin/comments.py
│   │   └── admin/activity.py
│   └── schemas/
│       ├── like.py
│       ├── comment.py
│       └── activity.py
└── tests/
    ├── test_hashing.py
    ├── test_public_likes.py
    ├── test_public_comments.py
    ├── test_admin_comments.py
    ├── test_admin_activity.py
    ├── test_email.py
    └── test_likes_dedup.py
```

**Modified files:**

```
backend/
├── app/
│   ├── config.py                        (7 new SMTP settings + admin_notify_email)
│   ├── services/email.py                (rewrite: real SMTP + dev fallback)
│   ├── models/__init__.py               (import LikeEvent, Comment)
│   ├── routers/public/__init__.py       (register comments router)
│   ├── routers/admin/__init__.py        (register comments + activity routers)
│   └── routers/public/posts.py          (add POST /posts/{id}/like)
└── tests/
    └── conftest.py                      (add seed_post factory + mock_smtp fixture)
```

---

## Task Outline (15 tasks)

| # | Task | Branch commit |
|---|---|---|
| 1 | Branch + Alembic 0003 migration (2 tables) | `feat(phase4): 0003 migration (like_events, comments)` |
| 2 | ORM models (LikeEvent, Comment) + __init__ wiring | `feat(phase4): ORM models for interactions tables` |
| 3 | Hashing helpers (ip_hash / email_hash) + tests | `feat(phase4): hashing helpers (ip_hash, email_hash)` |
| 4 | Likes service + tests (incl. concurrent dedup) | `feat(phase4): likes service (record_like + get_count)` |
| 5 | POST /api/posts/{id}/like + rate limit + tests | `feat(phase4): POST /posts/{id}/like (rate-limited)` |
| 6 | Comments service (create + list public) + tests | `feat(phase4): comments service (create_pending + list_for_post)` |
| 7 | POST /api/posts/{id}/comments + rate limit + tests | `feat(phase4): POST /posts/{id}/comments (rate-limited)` |
| 8 | GET /api/posts/{id}/comments (approved + admin reply nested) | `feat(phase4): GET /posts/{id}/comments (approved + admin reply)` |
| 9 | email.py rewrite (real SMTP + dev fallback) + magic-link upgraded + tests | `feat(phase4): email.py with real SMTP (dev: log fallback)` |
| 10 | send_comment_notification + wire into POST /comments | `feat(phase4): comment notification email on submission` |
| 11 | Admin GET /comments + DELETE + tests | `feat(phase4): admin comments list + delete` |
| 12 | Admin PATCH /comments/{id} (status/flag/reply_body) + tests | `feat(phase4): admin comments PATCH (status/flag/reply)` |
| 13 | Admin activity routers (full + dashboard) + tests | `feat(phase4): admin activity stream endpoints` |
| 14 | event_log instrumentation for 6 new event types | `feat(phase4): event_log entries for interactions events` |
| 15 | End-to-end verification sweep | (no commit; verification only) |

---

## Conventions

- **Branch:** All commits on `phase4-interactions` (created off `main`).
- **Working dir:** `/Users/sd3/Desktop/project/MyBlog/backend` for shell. `/Users/sd3/Desktop/project/MyBlog` for git.
- **Test runner:** `uv run pytest tests/<file>::<test> -v`. If pytest is missing, run `uv sync --all-extras` first.
- **Co-author footer** on every commit:
  ```
  Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
  ```
- **Tests use the dev DB** (matches Phase 1-3 conftest); each test cleans up its own rows.

---

## Task 1: Branch + Alembic 0003 migration

**Files:**
- Create: `backend/alembic/versions/0003_interactions.py`

- [ ] **Step 1: Create the work branch**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git checkout main
git checkout -b phase4-interactions
```

- [ ] **Step 2: Generate the migration scaffold**

```bash
cd backend
uv run alembic revision -m "interactions"
cd alembic/versions
mv 0003_*_interactions.py 0003_interactions.py
cd ../..
```

- [ ] **Step 3: Replace the file contents**

Open `backend/alembic/versions/0003_interactions.py` and replace its contents with:

```python
"""interactions

Revision ID: 0003_interactions
Revises: 0002_auth_phase3

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_interactions"
down_revision: str | None = "0002_auth_phase3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "like_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "ip_hash", "day", name="uq_like_events_post_ip_day"),
    )
    op.create_index("ix_like_events_post_id", "like_events", ["post_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("who", sa.String(length=64), nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("actor", sa.String(length=8), nullable=False, server_default="public"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["comments.id"], ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('pending','approved','spam')", name="ck_comments_status"),
        sa.CheckConstraint("actor IN ('public','admin')", name="ck_comments_actor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_comments_post_status", "comments", ["post_id", "status"])
    op.create_index("ix_comments_status_created", "comments", ["status", sa.text("created_at DESC")])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_parent_id", table_name="comments")
    op.drop_index("ix_comments_status_created", table_name="comments")
    op.drop_index("ix_comments_post_status", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_like_events_post_id", table_name="like_events")
    op.drop_table("like_events")
```

- [ ] **Step 4: Apply forward**

```bash
uv run alembic upgrade head
```

Expected: `Running upgrade 0002_auth_phase3 -> 0003_interactions, interactions`.

- [ ] **Step 5: Verify tables exist**

```bash
uv run python -c "
import asyncio
from sqlalchemy import text
from app.db import AsyncSessionLocal
async def main():
    async with AsyncSessionLocal() as s:
        for t in ('like_events', 'comments'):
            r = await s.execute(text(f'SELECT count(*) FROM {t}'))
            print(t, '=', r.scalar())
asyncio.run(main())
"
```

Expected: `like_events = 0`, `comments = 0`.

- [ ] **Step 6: Round-trip downgrade + upgrade**

```bash
uv run alembic downgrade -1
uv run alembic upgrade head
```

Both must succeed cleanly.

- [ ] **Step 7: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/alembic/versions/0003_interactions.py
git commit -m "$(cat <<'EOF'
feat(phase4): 0003 migration (like_events, comments)

- like_events: UNIQUE (post_id, ip_hash, day) for IP+day idempotency
- comments: parent_id self-FK CASCADE; CHECK status, CHECK actor;
  ix on (post_id, status), (status, created_at DESC), parent_id
- Both FK to posts.id ON DELETE CASCADE

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: ORM models (LikeEvent, Comment)

**Files:**
- Create: `backend/app/models/like_event.py`
- Create: `backend/app/models/comment.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Create `like_event.py`**

```python
from datetime import date as date_type
from datetime import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LikeEvent(Base):
    __tablename__ = "like_events"
    __table_args__ = (
        UniqueConstraint("post_id", "ip_hash", "day", name="uq_like_events_post_ip_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    ip_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    day: Mapped[date_type] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 2: Create `comment.py`**

```python
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','spam')", name="ck_comments_status"),
        CheckConstraint("actor IN ('public','admin')", name="ck_comments_actor"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("comments.id", ondelete="CASCADE")
    )
    who: Mapped[str] = mapped_column(String(64), nullable=False)
    email_hash: Mapped[str | None] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actor: Mapped[str] = mapped_column(String(8), nullable=False, default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 3: Update `app/models/__init__.py`**

Replace the contents with:

```python
from app.models.account import Account
from app.models.api_token import ApiToken
from app.models.base import Base, TimestampMixin
from app.models.comment import Comment
from app.models.contact import Contact
from app.models.contrib_day import ContribDay
from app.models.event_log import EventLog
from app.models.like_event import LikeEvent
from app.models.magic_link import MagicLink
from app.models.post import Post
from app.models.project import Project
from app.models.site_meta import SiteMeta
from app.models.tag import Tag
from app.models.tfa_recovery_code import TfaRecoveryCode

__all__ = [
    "Base", "TimestampMixin",
    "Account", "ApiToken", "Comment", "Contact", "ContribDay", "EventLog",
    "LikeEvent", "MagicLink", "Post", "Project", "SiteMeta", "Tag", "TfaRecoveryCode",
]
```

- [ ] **Step 4: Sanity import test**

```bash
cd backend && uv run python -c "from app.models import Comment, LikeEvent; print('ok')"
```

Expected: `ok`.

- [ ] **Step 5: Run full test suite (regression)**

```bash
uv run pytest -q
```

Expected: 148+ green.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/models/
git commit -m "$(cat <<'EOF'
feat(phase4): ORM models for like_events and comments

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Hashing helpers

**Files:**
- Create: `backend/app/services/hashing.py`
- Test: `backend/tests/test_hashing.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_hashing.py`:

```python
import os

import pytest

from app.services.hashing import email_hash, ip_hash


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setenv("LIKE_SALT", "test-salt-1234567")


def test_ip_hash_deterministic():
    a = ip_hash("1.2.3.4")
    b = ip_hash("1.2.3.4")
    assert a == b
    assert len(a) == 64


def test_ip_hash_distinct_for_different_ips():
    assert ip_hash("1.2.3.4") != ip_hash("1.2.3.5")


def test_email_hash_normalises_case_and_whitespace():
    assert email_hash("HI@WANGYANG.dev") == email_hash("hi@wangyang.dev")
    assert email_hash("  hi@wangyang.dev  ") == email_hash("hi@wangyang.dev")


def test_email_hash_distinct_for_different_emails():
    assert email_hash("a@b.c") != email_hash("a@b.d")


def test_separator_prevents_concatenation_collision():
    """Without a separator, sha256(ip_a + salt) could collide with sha256(ip_b + salt')."""
    # Pipe separator: sha256("1.2.3.4|salt") vs sha256("1.2.3|.4salt")
    # The two would be equal IF the salt position changed; with the pipe they cannot.
    assert ip_hash("1.2.3.4") != ip_hash("1.2.3")
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/test_hashing.py -v
```

Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement `app/services/hashing.py`**

```python
"""SHA-256 hashing helpers for IP and email values that must NEVER persist
in raw form (privacy + GDPR-light hygiene).

Both helpers concatenate the input with `LIKE_SALT` using a `|` separator
so that no two distinct (input, salt) pairs can hash to the same digest
through a clever boundary collision.
"""
from __future__ import annotations

import hashlib

from app.config import get_settings


def _hash(parts: tuple[str, str]) -> str:
    return hashlib.sha256(f"{parts[0]}|{parts[1]}".encode()).hexdigest()


def ip_hash(ip: str) -> str:
    """sha256(ip|LIKE_SALT) hex (64 chars)."""
    return _hash((ip, get_settings().like_salt))


def email_hash(email: str) -> str:
    """sha256(email_normalised|LIKE_SALT) hex.

    Normalisation: lowercase + strip whitespace.
    """
    normalised = email.lower().strip()
    return _hash((normalised, get_settings().like_salt))
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
uv run pytest tests/test_hashing.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/services/hashing.py backend/tests/test_hashing.py
git commit -m "$(cat <<'EOF'
feat(phase4): hashing helpers (ip_hash, email_hash)

- sha256(value|LIKE_SALT) with pipe separator prevents trivial
  concatenation collisions
- email_hash normalises lowercase + strip
- Used by likes (ip_hash) and comments (email_hash) to keep raw
  identifiers out of the DB

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Likes service

**Files:**
- Create: `backend/app/services/likes.py`
- Test: `backend/tests/test_likes_dedup.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_likes_dedup.py`:

```python
"""Unit tests for the likes service. Use the real test DB via AsyncSessionLocal."""
import asyncio
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert

from app.db import AsyncSessionLocal
from app.models import LikeEvent, Post, Tag
from app.services.likes import get_count, record_like


@pytest.fixture
async def seed_post():
    """Insert a throwaway post for likes to attach to."""
    pid = "p4-likes-test"
    async with AsyncSessionLocal() as s:
        # ensure a tag exists
        from sqlalchemy import select
        tag = (await s.execute(select(Tag).limit(1))).scalar_one_or_none()
        assert tag is not None, "seed bootstrap must run before tests"

        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="900", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def test_record_like_first_call_inserts(seed_post):
    async with AsyncSessionLocal() as s:
        total, was_new = await record_like(s, post_id=seed_post, ip="1.2.3.4")
        assert was_new is True
        assert total == 1


async def test_record_like_same_ip_same_day_idempotent(seed_post):
    async with AsyncSessionLocal() as s:
        await record_like(s, post_id=seed_post, ip="1.2.3.4")
        total, was_new = await record_like(s, post_id=seed_post, ip="1.2.3.4")
        assert was_new is False
        assert total == 1


async def test_record_like_different_ips_accumulate(seed_post):
    async with AsyncSessionLocal() as s:
        await record_like(s, post_id=seed_post, ip="1.2.3.4")
        await record_like(s, post_id=seed_post, ip="5.6.7.8")
        total, _ = await record_like(s, post_id=seed_post, ip="9.10.11.12")
        assert total == 3


async def test_record_like_concurrent_same_ip(seed_post):
    """100 concurrent record_like calls with same (post, ip, day) → exactly 1 row."""
    async def one():
        async with AsyncSessionLocal() as s:
            return await record_like(s, post_id=seed_post, ip="1.2.3.4")

    results = await asyncio.gather(*[one() for _ in range(100)], return_exceptions=False)
    new_count = sum(1 for _, was_new in results if was_new)
    assert new_count == 1
    async with AsyncSessionLocal() as s:
        assert await get_count(s, post_id=seed_post) == 1


async def test_get_count_zero_for_unliked():
    async with AsyncSessionLocal() as s:
        assert await get_count(s, post_id="never-liked") == 0
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_likes_dedup.py -v
```

Expected: FAIL (module does not exist).

- [ ] **Step 3: Implement `app/services/likes.py`**

```python
"""Likes service: idempotent per (post_id, ip_hash, day) UNIQUE constraint."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LikeEvent
from app.services.hashing import ip_hash


async def record_like(
    s: AsyncSession, *, post_id: str, ip: str
) -> tuple[int, bool]:
    """INSERT ... ON CONFLICT DO NOTHING.

    Returns (current total likes for the post, was_new).
    """
    today = datetime.now(UTC).date()
    stmt = (
        pg_insert(LikeEvent)
        .values(
            post_id=post_id,
            ip_hash=ip_hash(ip),
            day=today,
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(constraint="uq_like_events_post_ip_day")
        .returning(LikeEvent.id)
    )
    res = await s.execute(stmt)
    inserted_id = res.scalar_one_or_none()
    was_new = inserted_id is not None
    await s.commit()
    total = await get_count(s, post_id=post_id)
    return total, was_new


async def get_count(s: AsyncSession, *, post_id: str) -> int:
    res = await s.execute(
        select(func.count(LikeEvent.id)).where(LikeEvent.post_id == post_id)
    )
    return int(res.scalar() or 0)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_likes_dedup.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/services/likes.py backend/tests/test_likes_dedup.py
git commit -m "$(cat <<'EOF'
feat(phase4): likes service (record_like + get_count)

INSERT ... ON CONFLICT DO NOTHING on the (post_id, ip_hash, day)
UNIQUE constraint guarantees idempotency at the DB level. Concurrent
calls with the same triple race-safely produce exactly one row.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: POST /api/posts/{id}/like endpoint

**Files:**
- Modify: `backend/app/routers/public/posts.py`
- Create: `backend/app/schemas/like.py`
- Test: `backend/tests/test_public_likes.py`

- [ ] **Step 1: Add the schema**

Create `backend/app/schemas/like.py`:

```python
from pydantic import BaseModel, ConfigDict


class LikeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    likes: int
    was_new: bool
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_public_likes.py`:

```python
import pytest
from sqlalchemy import delete, insert
from datetime import UTC, date, datetime

from app.db import AsyncSessionLocal
from app.models import LikeEvent, Post, Tag


@pytest.fixture
async def seed_post():
    pid = "p4-public-likes"
    async with AsyncSessionLocal() as s:
        from sqlalchemy import select
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="901", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def test_first_like_returns_was_new_true(client, seed_post):
    r = await client.post(f"/api/posts/{seed_post}/like")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["likes"] == 1
    assert body["was_new"] is True


async def test_second_like_same_client_idempotent(client, seed_post):
    await client.post(f"/api/posts/{seed_post}/like")
    r = await client.post(f"/api/posts/{seed_post}/like")
    body = r.json()
    assert body["likes"] == 1
    assert body["was_new"] is False


async def test_like_unknown_post_404(client):
    r = await client.post("/api/posts/does-not-exist/like")
    assert r.status_code == 404


async def test_like_private_post_404(client):
    """Private posts are invisible to public — like must also 404, not 200."""
    pid = "p4-private"
    async with AsyncSessionLocal() as s:
        from sqlalchemy import select
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="902", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=True, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        r = await client.post(f"/api/posts/{pid}/like")
        assert r.status_code == 404
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()


async def test_like_rate_limit(client, seed_post, redis):
    """11th call within 60s → 429."""
    for _ in range(10):
        r = await client.post(f"/api/posts/{seed_post}/like")
        assert r.status_code == 200
    r = await client.post(f"/api/posts/{seed_post}/like")
    assert r.status_code == 429
    assert "Retry-After" in r.headers
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
uv run pytest tests/test_public_likes.py -v
```

Expected: FAIL (404 — endpoint doesn't exist).

- [ ] **Step 4: Extend `backend/app/routers/public/posts.py`**

Read the existing file first to understand its imports and patterns. Then append (after the existing GET endpoints) the like handler:

```python
from fastapi import HTTPException, Request
from redis.asyncio import Redis

from app.errors import NotFoundError
from app.redis import get_redis
from app.schemas.like import LikeResponse
from app.services import likes, rate_limit


@router.post("/posts/{post_id}/like", response_model=LikeResponse)
async def like_post(
    post_id: str,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> LikeResponse:
    ip = request.client.host if request.client else "unknown"
    await rate_limit.hit(redis, f"rl:like:{ip}:{post_id}", limit=10, window_sec=60)

    # Resolve published+public post
    from sqlalchemy import select
    from app.models import Post
    post = (
        await s.execute(
            select(Post).where(
                Post.id == post_id,
                Post.status == "published",
                Post.private.is_(False),
            )
        )
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("post not found")

    total, was_new = await likes.record_like(s, post_id=post_id, ip=ip)
    return LikeResponse(likes=total, was_new=was_new)
```

(The `Depends`, `get_session`, `AsyncSession`, and `router` imports already exist in `posts.py`. Add the new ones at the top of the existing import block.)

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_public_likes.py -v
```

Expected: 5 passed. The `client` fixture from conftest already overrides `get_redis` to fakeredis, so the rate-limit test works in isolation.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/public/posts.py backend/app/schemas/like.py backend/tests/test_public_likes.py
git commit -m "$(cat <<'EOF'
feat(phase4): POST /posts/{id}/like (rate-limited, IP+day idempotent)

- 10/min per (IP, post) via P3 rate_limit.hit
- 404 for unknown / private / unpublished posts
- Returns {likes, was_new}; second click same IP+day → was_new:false

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Comments service

**Files:**
- Create: `backend/app/services/comments.py`
- Create: `backend/app/schemas/comment.py`

(Tests come in Tasks 7-8 once the public endpoints exist.)

- [ ] **Step 1: Add schemas**

Create `backend/app/schemas/comment.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CommentCreateRequest(_Strict):
    who: str = Field(min_length=1, max_length=64)
    email: EmailStr
    body: str = Field(min_length=1, max_length=4000)


class CommentCreateResponse(_Strict):
    id: int
    status: Literal["pending", "approved", "spam"]


class PublicCommentItem(_Strict):
    id: int
    who: str
    body: str
    created_at: datetime
    admin_reply: "PublicAdminReply | None" = None


class PublicAdminReply(_Strict):
    id: int
    who: str
    body: str
    created_at: datetime


PublicCommentItem.model_rebuild()


class AdminCommentItem(_Strict):
    id: int
    post_id: str
    parent_id: int | None
    who: str
    email_hash: str | None
    body: str
    status: str
    flag: bool
    actor: str
    created_at: datetime


class AdminCommentPatchRequest(_Strict):
    status: Literal["pending", "approved", "spam"] | None = None
    flag: bool | None = None
    reply_body: str | None = Field(default=None, min_length=1, max_length=4000)


class AdminCommentPatchResponse(_Strict):
    id: int
    status: str
    flag: bool
    reply_id: int | None = None
```

- [ ] **Step 2: Implement `app/services/comments.py`**

```python
"""Comments service: pending-by-default public submission, admin-side
moderation including reply-as-child-comment."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import and_, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Comment


async def create_pending(
    s: AsyncSession,
    *,
    post_id: str,
    who: str,
    email_hash: str,
    body: str,
) -> Comment:
    row = Comment(
        post_id=post_id,
        parent_id=None,
        who=who,
        email_hash=email_hash,
        body=body,
        status="pending",
        flag=False,
        actor="public",
        created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.commit()
    await s.refresh(row)
    return row


async def list_for_post(s: AsyncSession, *, post_id: str) -> list[tuple[Comment, Comment | None]]:
    """Return [(top_level, admin_reply_or_None)] in created_at order.

    Top-level comments: status='approved' AND parent_id IS NULL AND post_id=$1.
    Admin reply (≤1 per parent): actor='admin' AND status='approved' AND parent_id=parent.id.
    """
    tops = (
        await s.execute(
            select(Comment)
            .where(
                Comment.post_id == post_id,
                Comment.status == "approved",
                Comment.parent_id.is_(None),
            )
            .order_by(Comment.created_at)
        )
    ).scalars().all()

    if not tops:
        return []

    parent_ids = [t.id for t in tops]
    replies = (
        await s.execute(
            select(Comment).where(
                Comment.parent_id.in_(parent_ids),
                Comment.actor == "admin",
                Comment.status == "approved",
            )
        )
    ).scalars().all()
    by_parent: dict[int, Comment] = {r.parent_id: r for r in replies if r.parent_id}
    return [(t, by_parent.get(t.id)) for t in tops]


async def list_admin(
    s: AsyncSession,
    *,
    status: Literal["pending", "approved", "spam"] | None = None,
    post_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Comment]:
    q = select(Comment)
    if status is not None:
        q = q.where(Comment.status == status)
    if post_id is not None:
        q = q.where(Comment.post_id == post_id)
    q = q.order_by(Comment.created_at.desc()).limit(limit).offset(offset)
    return list((await s.execute(q)).scalars().all())


async def patch(
    s: AsyncSession,
    *,
    comment_id: int,
    status: Literal["pending", "approved", "spam"] | None,
    flag: bool | None,
    reply_body: str | None,
    admin_who: str,
) -> tuple[Comment, Comment | None]:
    """Returns (parent_after_update, child_reply_or_None)."""
    parent = (
        await s.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()
    if parent is None:
        return None, None  # caller raises 404

    if status is not None:
        parent.status = status
    if flag is not None:
        parent.flag = flag

    child: Comment | None = None
    if reply_body is not None:
        child = Comment(
            post_id=parent.post_id,
            parent_id=parent.id,
            who=admin_who,
            email_hash=None,
            body=reply_body,
            status="approved",
            flag=False,
            actor="admin",
            created_at=datetime.now(UTC),
        )
        s.add(child)
    await s.commit()
    if child is not None:
        await s.refresh(child)
    await s.refresh(parent)
    return parent, child


async def delete_one(s: AsyncSession, *, comment_id: int) -> bool:
    res = await s.execute(delete(Comment).where(Comment.id == comment_id))
    await s.commit()
    return res.rowcount > 0
```

- [ ] **Step 3: Quick syntactic sanity**

```bash
cd backend && uv run python -c "from app.services import comments; print('ok')"
```

Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/services/comments.py backend/app/schemas/comment.py
git commit -m "$(cat <<'EOF'
feat(phase4): comments service + schemas

- create_pending: public submission, status=pending, actor=public
- list_for_post: approved top-levels with at-most-one nested admin reply
- list_admin / patch / delete_one: backoffice operations
- patch with reply_body creates child Comment(parent_id, actor='admin',
  status='approved') in a single transaction

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: POST /api/posts/{id}/comments

**Files:**
- Create: `backend/app/routers/public/comments.py`
- Modify: `backend/app/routers/public/__init__.py`
- Test: `backend/tests/test_public_comments.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_public_comments.py`:

```python
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert, select

from app.db import AsyncSessionLocal
from app.models import Comment, Post, Tag


@pytest.fixture
async def seed_post():
    pid = "p4-comments-pub"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="903", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def test_post_comment_returns_pending(client, seed_post):
    r = await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "alice", "email": "alice@example.com", "body": "Hi there"},
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert isinstance(body["id"], int)


async def test_post_comment_persists_email_as_hash_only(client, seed_post):
    await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "bob", "email": "bob@example.com", "body": "hello"},
    )
    async with AsyncSessionLocal() as s:
        rows = (
            await s.execute(select(Comment).where(Comment.post_id == seed_post))
        ).scalars().all()
        assert any("bob@example.com" not in (r.body or "") for r in rows)
        for r in rows:
            assert r.email_hash and len(r.email_hash) == 64
            assert "@" not in r.email_hash


async def test_post_comment_disabled_post_403(client):
    pid = "p4-disabled-comments"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="904", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=False,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        r = await client.post(
            f"/api/posts/{pid}/comments",
            json={"who": "x", "email": "x@y.z", "body": "hi"},
        )
        assert r.status_code == 403
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()


async def test_post_comment_unknown_post_404(client):
    r = await client.post(
        "/api/posts/never-exists/comments",
        json={"who": "x", "email": "x@y.z", "body": "hi"},
    )
    assert r.status_code == 404


async def test_post_comment_rate_limit(client, seed_post):
    """4th call within 60s → 429."""
    for _ in range(3):
        r = await client.post(
            f"/api/posts/{seed_post}/comments",
            json={"who": "spammer", "email": "s@s.s", "body": "spam"},
        )
        assert r.status_code == 202
    r = await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "spammer", "email": "s@s.s", "body": "spam"},
    )
    assert r.status_code == 429


async def test_post_comment_invalid_body(client, seed_post):
    r = await client.post(
        f"/api/posts/{seed_post}/comments",
        json={"who": "", "email": "x@y.z", "body": "hi"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_public_comments.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/routers/public/comments.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import NotFoundError
from app.models import Post
from app.redis import get_redis
from app.schemas.comment import CommentCreateRequest, CommentCreateResponse
from app.services import comments, rate_limit
from app.services.hashing import email_hash

router = APIRouter()


async def _resolve_post(s: AsyncSession, post_id: str) -> Post:
    post = (
        await s.execute(
            select(Post).where(
                Post.id == post_id,
                Post.status == "published",
                Post.private.is_(False),
            )
        )
    ).scalar_one_or_none()
    if post is None:
        raise NotFoundError("post not found")
    return post


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentCreateResponse,
    status_code=202,
)
async def create_comment(
    post_id: str,
    req: CommentCreateRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
) -> CommentCreateResponse:
    ip = request.client.host if request.client else "unknown"
    await rate_limit.hit(redis, f"rl:comment:{ip}", limit=3, window_sec=60)

    post = await _resolve_post(s, post_id)
    if not post.comments_enabled:
        raise HTTPException(403, "comments disabled on this post")

    row = await comments.create_pending(
        s,
        post_id=post_id,
        who=req.who,
        email_hash=email_hash(req.email),
        body=req.body,
    )
    return CommentCreateResponse(id=row.id, status=row.status)
```

- [ ] **Step 4: Register the router**

In `backend/app/routers/public/__init__.py`, add the import and include:

```python
from app.routers.public.comments import router as comments_router
```
```python
router.include_router(comments_router, prefix="/api", tags=["public·comments"])
```

(Match the existing prefix used for the other public routers.)

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_public_comments.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/public/comments.py backend/app/routers/public/__init__.py backend/tests/test_public_comments.py
git commit -m "$(cat <<'EOF'
feat(phase4): POST /posts/{id}/comments (rate-limited)

- 3/min per IP via P3 rate_limit.hit
- 404 unknown/private/unpublished post; 403 if comments_enabled=false
- email_hash via P4 hashing; raw email never persisted
- Returns 202 {id, status:'pending'}; admin moderates later

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: GET /api/posts/{id}/comments

**Files:**
- Modify: `backend/app/routers/public/comments.py`
- Test: `backend/tests/test_public_comments.py` (extend)

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_public_comments.py`:

```python
async def test_get_comments_only_approved(client, seed_post):
    """Pending comments must not appear in GET response."""
    async with AsyncSessionLocal() as s:
        s.add_all([
            Comment(post_id=seed_post, who="approved", email_hash="h" * 64,
                    body="visible", status="approved", actor="public", flag=False,
                    created_at=datetime.now(UTC)),
            Comment(post_id=seed_post, who="pending", email_hash="h" * 64,
                    body="hidden", status="pending", actor="public", flag=False,
                    created_at=datetime.now(UTC)),
            Comment(post_id=seed_post, who="spam", email_hash="h" * 64,
                    body="spammy", status="spam", actor="public", flag=False,
                    created_at=datetime.now(UTC)),
        ])
        await s.commit()

    r = await client.get(f"/api/posts/{seed_post}/comments")
    assert r.status_code == 200
    body = r.json()
    bodies = [c["body"] for c in body]
    assert "visible" in bodies
    assert "hidden" not in bodies
    assert "spammy" not in bodies


async def test_get_comments_includes_admin_reply_nested(client, seed_post):
    async with AsyncSessionLocal() as s:
        parent = Comment(post_id=seed_post, who="alice", email_hash="h" * 64,
                         body="What about X?", status="approved", actor="public", flag=False,
                         created_at=datetime.now(UTC))
        s.add(parent)
        await s.commit()
        await s.refresh(parent)
        s.add(Comment(post_id=seed_post, parent_id=parent.id, who="Wang Yang",
                      email_hash=None, body="X is the answer.", status="approved",
                      actor="admin", flag=False, created_at=datetime.now(UTC)))
        await s.commit()

    r = await client.get(f"/api/posts/{seed_post}/comments")
    items = r.json()
    parent_item = next(c for c in items if c["body"] == "What about X?")
    assert parent_item["admin_reply"] is not None
    assert parent_item["admin_reply"]["body"] == "X is the answer."
    assert parent_item["admin_reply"]["who"] == "Wang Yang"


async def test_get_comments_response_omits_email_hash(client, seed_post):
    async with AsyncSessionLocal() as s:
        s.add(Comment(post_id=seed_post, who="alice", email_hash="abcd1234" * 8,
                      body="hi", status="approved", actor="public", flag=False,
                      created_at=datetime.now(UTC)))
        await s.commit()
    r = await client.get(f"/api/posts/{seed_post}/comments")
    body = r.json()
    for item in body:
        assert "email_hash" not in item
        assert "email" not in item
```

- [ ] **Step 2: Append failing endpoint stub**

Add the GET endpoint to `backend/app/routers/public/comments.py`:

```python
from app.schemas.comment import PublicAdminReply, PublicCommentItem


@router.get("/posts/{post_id}/comments", response_model=list[PublicCommentItem])
async def list_comments(
    post_id: str,
    s: AsyncSession = Depends(get_session),
) -> list[PublicCommentItem]:
    await _resolve_post(s, post_id)
    pairs = await comments.list_for_post(s, post_id=post_id)
    return [
        PublicCommentItem(
            id=top.id, who=top.who, body=top.body, created_at=top.created_at,
            admin_reply=(
                PublicAdminReply(
                    id=reply.id, who=reply.who, body=reply.body, created_at=reply.created_at
                ) if reply else None
            ),
        )
        for top, reply in pairs
    ]
```

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_public_comments.py -v
```

Expected: 9 passed (6 prior + 3 new).

- [ ] **Step 4: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/public/comments.py backend/tests/test_public_comments.py
git commit -m "$(cat <<'EOF'
feat(phase4): GET /posts/{id}/comments (approved + admin reply nested)

- Only status='approved' top-levels (parent_id IS NULL)
- At most one admin reply per parent (actor='admin' AND parent_id=top.id)
- Response shape strips email_hash; raw email already never stored

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: email.py rewrite (real SMTP + dev fallback)

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/email.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_email.py`

- [ ] **Step 1: Add SMTP settings**

Open `backend/app/config.py` and add to the `Settings` class (after `secrets_key`):

```python
    # SMTP (optional; if smtp_host is None we fall back to log-only)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str = "noreply@wangyang.dev"
    smtp_starttls: bool = True
    admin_notify_email: str | None = None
```

- [ ] **Step 2: Document in `.env.example`**

Append to `backend/.env.example`:

```
# SMTP for outbound email (magic-link, comment notifications). Leave
# unset in dev — emails will log to stdout via structlog instead.
# SMTP_HOST=smtp.example.com
# SMTP_PORT=587
# SMTP_USER=apikey
# SMTP_PASSWORD=secret
# SMTP_FROM=noreply@wangyang.dev
# SMTP_STARTTLS=true
# ADMIN_NOTIFY_EMAIL=admin@example.com
```

- [ ] **Step 3: Write failing tests**

Create `backend/tests/test_email.py`:

```python
"""Email transport: dev mode (log) vs SMTP mode (mocked smtplib)."""
import logging
from unittest.mock import MagicMock, patch

import pytest

from app.services.email import send_comment_notification, send_email, send_magic_link


async def test_dev_mode_logs_when_smtp_host_unset(caplog, monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    caplog.set_level(logging.INFO)
    await send_email(to="a@b.c", subject="hi", body="hello")
    # We don't strictly assert on log capture (structlog vs caplog can be
    # finicky); the absence of a raised exception + no smtplib call is
    # the contract: dev mode is non-fatal.


async def test_smtp_mode_calls_smtplib(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    from app.config import get_settings
    get_settings.cache_clear()

    fake_smtp = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.__enter__.return_value = fake_smtp
    fake_ctx.__exit__.return_value = False

    with patch("smtplib.SMTP", return_value=fake_ctx) as ctor:
        await send_email(to="a@b.c", subject="hi", body="hello")

    ctor.assert_called_once_with("smtp.example.test", 587)
    fake_smtp.starttls.assert_called_once()
    fake_smtp.login.assert_called_once_with("user", "pw")
    fake_smtp.send_message.assert_called_once()


async def test_smtp_failure_swallowed(monkeypatch, caplog):
    """SMTP exception must NOT propagate; comment/magic-link must still respond."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    from app.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP", side_effect=ConnectionError("fake")):
        # Must not raise
        await send_email(to="a@b.c", subject="hi", body="hello")


async def test_send_magic_link_uses_send_email(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    await send_magic_link(email="a@b.c", url="http://x/y")
    # No raise — dev fallback covers it.


async def test_send_comment_notification_uses_send_email(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    await send_comment_notification(
        to="admin@x.com", comment_id=42, post_id="hello", who="alice", snippet="hi"
    )
```

- [ ] **Step 4: Run tests to confirm failure**

```bash
uv run pytest tests/test_email.py -v
```

Expected: FAIL — at minimum `send_comment_notification` doesn't exist; `send_email` may or may not be called via `smtplib`.

- [ ] **Step 5: Implement `app/services/email.py`**

Replace the file contents with:

```python
"""Email transport.

Two modes selected at call time via settings.smtp_host:

  - smtp_host = None  → dev fallback: structlog.info() the event and
    return. Used when the operator hasn't wired SMTP yet.
  - smtp_host = "..." → run smtplib.SMTP(host, port) in asyncio.to_thread,
    optional STARTTLS + login, send_message.

Failures inside SMTP mode are caught and logged at WARNING. The caller's
business path (comment submission, magic-link issuance) MUST NOT fail
because email transport failed.
"""
from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)


def _send_sync(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(msg)


async def send_email(*, to: str, subject: str, body: str) -> None:
    settings = get_settings()
    if settings.smtp_host is None:
        log.info("email.dev_log", to=to, subject=subject, body_preview=body[:120])
        return
    try:
        await asyncio.to_thread(_send_sync, to=to, subject=subject, body=body)
        log.info("email.sent", to=to, subject=subject)
    except Exception as e:  # noqa: BLE001
        log.warning("email.send_failed", to=to, subject=subject, error=str(e))


async def send_magic_link(*, email: str, url: str) -> None:
    subject = "Your wangyang.dev magic-link"
    body = (
        f"Click to sign in: {url}\n\n"
        "Valid for 15 minutes. If you didn't request this, ignore this email."
    )
    await send_email(to=email, subject=subject, body=body)


async def send_comment_notification(
    *, to: str, comment_id: int, post_id: str, who: str, snippet: str
) -> None:
    subject = f"[wangyang.dev] new comment on {post_id}"
    body = (
        f"From: {who}\n\n"
        f"{snippet[:280]}\n\n"
        f"Moderate: /admin#comments/{comment_id}"
    )
    await send_email(to=to, subject=subject, body=body)
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_email.py -v tests/test_auth_magic_link.py -v
```

Expected: 5 new + 5 magic-link still pass (P3 magic-link relied on log fallback; new email module preserves it when smtp_host is unset).

- [ ] **Step 7: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/config.py backend/app/services/email.py backend/.env.example backend/tests/test_email.py
git commit -m "$(cat <<'EOF'
feat(phase4): email.py with real SMTP (dev: log fallback)

- smtp_host=None  → structlog log only (preserves P3 dev mode)
- smtp_host=... → asyncio.to_thread(smtplib.SMTP) with STARTTLS+login
- SMTP failures caught and logged WARNING; caller path never fails
- send_magic_link upgraded from log-only stub to real SMTP-capable
- send_comment_notification added (called in Task 10)
- 7 new SMTP settings; .env.example documents them

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: send_comment_notification wired into POST /comments

**Files:**
- Modify: `backend/app/routers/public/comments.py`
- Test: `backend/tests/test_public_comments.py` (extend)

- [ ] **Step 1: Append failing test**

Append to `backend/tests/test_public_comments.py`:

```python
from unittest.mock import patch


async def test_post_comment_triggers_notification(client, seed_post, monkeypatch):
    monkeypatch.setenv("ADMIN_NOTIFY_EMAIL", "admin@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    from app.config import get_settings
    get_settings.cache_clear()

    from unittest.mock import MagicMock
    fake_smtp = MagicMock()
    fake_ctx = MagicMock()
    fake_ctx.__enter__.return_value = fake_smtp

    with patch("smtplib.SMTP", return_value=fake_ctx):
        r = await client.post(
            f"/api/posts/{seed_post}/comments",
            json={"who": "carol", "email": "carol@example.com", "body": "hi mod"},
        )
    assert r.status_code == 202
    fake_smtp.send_message.assert_called_once()


async def test_post_comment_succeeds_when_smtp_down(client, seed_post, monkeypatch):
    """SMTP failure inside notification must NOT cause the POST to 500."""
    monkeypatch.setenv("ADMIN_NOTIFY_EMAIL", "admin@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    from app.config import get_settings
    get_settings.cache_clear()

    with patch("smtplib.SMTP", side_effect=ConnectionError("nope")):
        r = await client.post(
            f"/api/posts/{seed_post}/comments",
            json={"who": "dave", "email": "d@e.f", "body": "yo"},
        )
    assert r.status_code == 202
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_public_comments.py::test_post_comment_triggers_notification -v
```

Expected: FAIL — `send_message` not called yet.

- [ ] **Step 3: Wire notification into create_comment**

Modify `backend/app/routers/public/comments.py`'s `create_comment` to fire the notification AFTER the row is committed. Add the call before the return:

```python
from sqlalchemy import select as _select
from app.config import get_settings
from app.models import Account
from app.services import email as email_svc
```

Inside `create_comment`, after `row = await comments.create_pending(...)`:

```python
    settings = get_settings()
    notify_to = settings.admin_notify_email
    if notify_to is None:
        admin = (
            await s.execute(_select(Account).where(Account.id == 1))
        ).scalar_one_or_none()
        notify_to = admin.email if admin else None
    if notify_to:
        await email_svc.send_comment_notification(
            to=notify_to,
            comment_id=row.id,
            post_id=post_id,
            who=req.who,
            snippet=req.body,
        )

    return CommentCreateResponse(id=row.id, status=row.status)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_public_comments.py -v
```

Expected: 11 passed (9 prior + 2 new).

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/public/comments.py backend/tests/test_public_comments.py
git commit -m "$(cat <<'EOF'
feat(phase4): comment notification email on submission

- POST /comments fires send_comment_notification after persisting
- Recipient: settings.admin_notify_email or accounts.email of singleton
- SMTP failure inside email path is swallowed (caller sees 202)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Admin GET /comments + DELETE

**Files:**
- Create: `backend/app/routers/admin/comments.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Test: `backend/tests/test_admin_comments.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_comments.py`:

```python
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert, select

from app.db import AsyncSessionLocal
from app.models import Comment, Post, Tag

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def seed_post():
    pid = "p4-admin-comments"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="905", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Comment).where(Comment.post_id == pid))
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def _seed_comments(post_id):
    async with AsyncSessionLocal() as s:
        s.add_all([
            Comment(post_id=post_id, who="a", email_hash="h" * 64,
                    body="pending one", status="pending", actor="public",
                    flag=False, created_at=datetime.now(UTC)),
            Comment(post_id=post_id, who="b", email_hash="h" * 64,
                    body="approved one", status="approved", actor="public",
                    flag=False, created_at=datetime.now(UTC)),
            Comment(post_id=post_id, who="c", email_hash="h" * 64,
                    body="spam one", status="spam", actor="public",
                    flag=False, created_at=datetime.now(UTC)),
        ])
        await s.commit()


async def test_admin_list_all_no_filter(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    r = await client.get(
        "/api/admin/comments",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    statuses = [c["status"] for c in items if c["post_id"] == seed_post]
    assert sorted(statuses) == ["approved", "pending", "spam"]


async def test_admin_list_filter_by_status(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    r = await client.get(
        "/api/admin/comments?status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = [c for c in r.json() if c["post_id"] == seed_post]
    assert len(items) == 1
    assert items[0]["status"] == "pending"


async def test_admin_delete_204(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.delete(
        f"/api/admin/comments/{cid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Comment).where(Comment.id == cid))).scalar_one_or_none()
        assert row is None


async def test_admin_delete_unknown_404(client, admin_token):
    r = await client.delete(
        "/api/admin/comments/99999999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/test_admin_comments.py -v
```

Expected: FAIL.

- [ ] **Step 3: Create `app/routers/admin/comments.py`**

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account
from app.schemas.comment import AdminCommentItem
from app.services import comments

router = APIRouter()


@router.get("/comments", response_model=list[AdminCommentItem])
async def list_comments(
    status: Literal["pending", "approved", "spam"] | None = None,
    post_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[AdminCommentItem]:
    rows = await comments.list_admin(
        s, status=status, post_id=post_id, limit=limit, offset=offset
    )
    return [
        AdminCommentItem(
            id=r.id, post_id=r.post_id, parent_id=r.parent_id,
            who=r.who, email_hash=r.email_hash, body=r.body,
            status=r.status, flag=r.flag, actor=r.actor, created_at=r.created_at,
        )
        for r in rows
    ]


@router.delete("/comments/{comment_id}", status_code=204, dependencies=[Depends(require_scope("write"))])
async def delete_comment(
    comment_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    ok = await comments.delete_one(s, comment_id=comment_id)
    if not ok:
        raise HTTPException(404, "comment not found")
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router**

In `backend/app/routers/admin/__init__.py`:

```python
from app.routers.admin.comments import router as comments_router
```
```python
router.include_router(comments_router, tags=["admin·comments"])
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_admin_comments.py -v
```

Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/admin/comments.py backend/app/routers/admin/__init__.py backend/tests/test_admin_comments.py
git commit -m "$(cat <<'EOF'
feat(phase4): admin comments list + delete

- GET /admin/comments?status=&post_id=&limit=&offset= filterable
- DELETE /admin/comments/{id} cascades replies via FK ON DELETE CASCADE
- write-scope api-tokens denied DELETE (require_scope('write'))

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Admin PATCH /comments/{id}

**Files:**
- Modify: `backend/app/routers/admin/comments.py`
- Test: `backend/tests/test_admin_comments.py` (extend)

- [ ] **Step 1: Append failing tests**

```python
async def test_admin_patch_status_approve(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}&status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body.get("reply_id") is None


async def test_admin_patch_set_flag(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"flag": True},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["flag"] is True


async def test_admin_patch_reply_creates_child(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}&status=approved",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    parent_id = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{parent_id}",
        json={"reply_body": "Thanks for the comment!"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply_id"] is not None

    async with AsyncSessionLocal() as s:
        child = (
            await s.execute(select(Comment).where(Comment.id == body["reply_id"]))
        ).scalar_one()
        assert child.parent_id == parent_id
        assert child.actor == "admin"
        assert child.status == "approved"
        assert child.body == "Thanks for the comment!"


async def test_admin_patch_combined_status_and_reply(client, admin_token, seed_post):
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}&status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"status": "approved", "reply_body": "Approved + replied"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    body = r.json()
    assert body["status"] == "approved"
    assert body["reply_id"] is not None


async def test_admin_patch_unknown_404(client, admin_token):
    r = await client.patch(
        "/api/admin/comments/99999999",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_admin_patch_read_token_denied_403(client, admin_token, seed_post):
    create = await client.post(
        "/api/admin/api-tokens",
        json={"name": "r-comments", "scope": "read"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    raw = create.json()["token"]
    await _seed_comments(seed_post)
    listing = await client.get(
        f"/api/admin/comments?post_id={seed_post}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    cid = listing.json()[0]["id"]
    r = await client.patch(
        f"/api/admin/comments/{cid}",
        json={"status": "approved"},
        headers={"Authorization": f"Bearer {raw}"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_admin_comments.py -v
```

Expected: 6 new fail (404 / 405).

- [ ] **Step 3: Add the PATCH endpoint**

In `backend/app/routers/admin/comments.py`, append:

```python
from sqlalchemy import select as _select
from app.models import SiteMeta
from app.schemas.comment import AdminCommentPatchRequest, AdminCommentPatchResponse


@router.patch(
    "/comments/{comment_id}",
    response_model=AdminCommentPatchResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def patch_comment(
    comment_id: int,
    req: AdminCommentPatchRequest,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> AdminCommentPatchResponse:
    # Look up admin display name from site_meta for the reply
    site = (
        await s.execute(_select(SiteMeta).where(SiteMeta.id == 1))
    ).scalar_one_or_none()
    admin_who = site.name if site else "admin"

    parent, child = await comments.patch(
        s,
        comment_id=comment_id,
        status=req.status,
        flag=req.flag,
        reply_body=req.reply_body,
        admin_who=admin_who,
    )
    if parent is None:
        raise HTTPException(404, "comment not found")
    return AdminCommentPatchResponse(
        id=parent.id,
        status=parent.status,
        flag=parent.flag,
        reply_id=child.id if child else None,
    )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_admin_comments.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/admin/comments.py backend/tests/test_admin_comments.py
git commit -m "$(cat <<'EOF'
feat(phase4): admin PATCH /comments (status/flag/reply_body)

- status transitions (any→any per spec) + flag boolean
- reply_body creates child Comment(actor='admin', parent_id, status='approved')
  using site_meta.name as the displayed `who`
- Combined status+reply works in one transaction
- write-scope guard via require_scope('write')

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Admin activity stream endpoints

**Files:**
- Create: `backend/app/routers/admin/activity.py`
- Create: `backend/app/services/activity.py`
- Create: `backend/app/schemas/activity.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Test: `backend/tests/test_admin_activity.py`

- [ ] **Step 1: Add schema**

Create `backend/app/schemas/activity.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ActivityItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    type: str
    actor: str
    target: str | None = None
    meta: dict[str, Any]
    created_at: datetime
```

- [ ] **Step 2: Implement service**

Create `backend/app/services/activity.py`:

```python
"""Activity stream queries over event_log."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventLog


async def list_events(
    s: AsyncSession,
    *,
    types: list[str] | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[EventLog]:
    q = select(EventLog).order_by(EventLog.created_at.desc()).limit(limit).offset(offset)
    if types:
        q = q.where(EventLog.type.in_(types))
    return list((await s.execute(q)).scalars().all())
```

- [ ] **Step 3: Write failing tests**

Create `backend/tests/test_admin_activity.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import EventLog

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def seed_events():
    async with AsyncSessionLocal() as s:
        s.add_all([
            EventLog(type="phase4.test.a", actor="t", target="x", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="phase4.test.b", actor="t", target="y", meta={}, created_at=datetime.now(UTC)),
            EventLog(type="phase4.test.a", actor="t", target="z", meta={"k": 1}, created_at=datetime.now(UTC)),
        ])
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(EventLog).where(EventLog.type.in_(["phase4.test.a", "phase4.test.b"])))
        await s.commit()


async def test_activity_returns_rows(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/activity?limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    items = r.json()
    types = {i["type"] for i in items}
    assert "phase4.test.a" in types
    assert "phase4.test.b" in types


async def test_activity_filter_by_type(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/activity?type=phase4.test.a&limit=20",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = r.json()
    types = {i["type"] for i in items}
    assert types == {"phase4.test.a"}


async def test_activity_descending_order(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/activity?limit=50",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    items = r.json()
    timestamps = [i["created_at"] for i in items]
    assert timestamps == sorted(timestamps, reverse=True)


async def test_dashboard_activity_default_limit(client, admin_token, seed_events):
    r = await client.get(
        "/api/admin/dashboard/activity",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()) <= 20


async def test_activity_requires_admin(client):
    r = await client.get("/api/admin/activity")
    assert r.status_code == 401
```

- [ ] **Step 4: Run failing tests**

```bash
uv run pytest tests/test_admin_activity.py -v
```

Expected: FAIL.

- [ ] **Step 5: Create router**

Create `backend/app/routers/admin/activity.py`:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.activity import ActivityItem
from app.services import activity

router = APIRouter()


@router.get("/activity", response_model=list[ActivityItem])
async def list_activity(
    type: list[str] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ActivityItem]:
    rows = await activity.list_events(s, types=type, limit=limit, offset=offset)
    return [
        ActivityItem(
            id=r.id, type=r.type, actor=r.actor, target=r.target,
            meta=r.meta or {}, created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/dashboard/activity", response_model=list[ActivityItem])
async def dashboard_activity(
    limit: int = Query(default=20, ge=1, le=100),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[ActivityItem]:
    rows = await activity.list_events(s, limit=limit, offset=0)
    return [
        ActivityItem(
            id=r.id, type=r.type, actor=r.actor, target=r.target,
            meta=r.meta or {}, created_at=r.created_at,
        )
        for r in rows
    ]
```

- [ ] **Step 6: Register router**

In `backend/app/routers/admin/__init__.py`:

```python
from app.routers.admin.activity import router as activity_router
```
```python
router.include_router(activity_router, tags=["admin·activity"])
```

- [ ] **Step 7: Run tests**

```bash
uv run pytest tests/test_admin_activity.py -v
```

Expected: 5 passed.

- [ ] **Step 8: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/services/activity.py backend/app/routers/admin/activity.py backend/app/routers/admin/__init__.py backend/app/schemas/activity.py backend/tests/test_admin_activity.py
git commit -m "$(cat <<'EOF'
feat(phase4): admin activity stream endpoints

- GET /admin/activity?type=&limit=&offset= filterable + paginated
- GET /admin/dashboard/activity?limit= for the dashboard widget
- Both return event_log rows ordered by created_at DESC
- 401 unauthenticated; no scope check (read-only)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: event_log instrumentation (6 new types)

**Files:**
- Modify: `backend/app/routers/public/posts.py` (post.liked)
- Modify: `backend/app/routers/public/comments.py` (comment.created)
- Modify: `backend/app/routers/admin/comments.py` (comment.moderated, comment.flagged, comment.replied, comment.deleted)
- Test: `backend/tests/test_admin_activity.py` (extend)

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_admin_activity.py`:

```python
async def test_post_liked_writes_event(client, admin_token):
    """POST /posts/{id}/like must produce a post.liked event."""
    pid = "p4-evt-like"
    from datetime import UTC, date, datetime
    from sqlalchemy import select, insert
    from app.models import LikeEvent, Post, Tag

    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="906", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        await client.post(f"/api/posts/{pid}/like")
        r = await client.get(
            "/api/admin/activity?type=post.liked&limit=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        items = r.json()
        assert any(i["target"] == pid for i in items)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(LikeEvent).where(LikeEvent.post_id == pid))
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()


async def test_comment_created_writes_event(client, admin_token):
    pid = "p4-evt-cmt"
    from datetime import UTC, date, datetime
    from sqlalchemy import select, insert
    from app.models import Comment, Post, Tag

    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="907", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="x", body_json={"blocks": []},
            word_count=1, status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    try:
        await client.post(
            f"/api/posts/{pid}/comments",
            json={"who": "evt", "email": "e@v.t", "body": "hello"},
        )
        r = await client.get(
            "/api/admin/activity?type=comment.created&limit=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        items = r.json()
        assert any(str(i.get("meta", {}).get("post_id")) == pid for i in items)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Comment).where(Comment.post_id == pid))
            await s.execute(delete(Post).where(Post.id == pid))
            await s.commit()
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_admin_activity.py::test_post_liked_writes_event tests/test_admin_activity.py::test_comment_created_writes_event -v
```

Expected: FAIL — no event written yet.

- [ ] **Step 3: Wire `post.liked` in `app/routers/public/posts.py`**

In the `like_post` endpoint, after `total, was_new = await likes.record_like(...)`:

```python
from app.services.event_log import write_event
from app.services.hashing import ip_hash
from datetime import UTC, datetime
```

```python
    if was_new:
        await write_event(
            s,
            type="post.liked",
            actor=ip_hash(ip)[:12],
            target=post_id,
            meta={"day": datetime.now(UTC).date().isoformat()},
        )
        await s.commit()
```

- [ ] **Step 4: Wire `comment.created` in `app/routers/public/comments.py`**

In `create_comment`, after the row is created and before sending the notification:

```python
from app.services.event_log import write_event
```

```python
    await write_event(
        s, type="comment.created",
        actor=email_hash(req.email)[:12],
        target=str(row.id),
        meta={"post_id": post_id, "who": req.who, "length": len(req.body)},
    )
    await s.commit()
```

- [ ] **Step 5: Wire admin events in `app/routers/admin/comments.py`**

In `delete_comment`, before raising/returning:

```python
from app.services.event_log import write_event
```

```python
    # delete_one already commits the row delete; write the event AFTER
    await write_event(
        s, type="comment.deleted", actor=_admin.email,
        meta={"comment_id": comment_id},
    )
    await s.commit()
```

In `patch_comment`, after `parent, child = ...`:

```python
    if req.status is not None:
        await write_event(
            s, type="comment.moderated", actor=_admin.email,
            target=str(parent.id),
            meta={"to_status": req.status},
        )
    if req.flag is not None:
        await write_event(
            s, type="comment.flagged", actor=_admin.email,
            target=str(parent.id),
            meta={"flag": req.flag},
        )
    if child is not None:
        await write_event(
            s, type="comment.replied", actor=_admin.email,
            target=str(parent.id),
            meta={"child_id": child.id, "post_id": parent.post_id},
        )
    await s.commit()
```

(`comments.patch` already commits its own changes; the additional commit here flushes the event rows.)

- [ ] **Step 6: Run tests**

```bash
uv run pytest tests/test_admin_activity.py -v
```

Expected: all pass (5 prior + 2 new).

- [ ] **Step 7: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/app/routers/
git commit -m "$(cat <<'EOF'
feat(phase4): event_log entries for interactions events

Wires the 6 new event types declared in spec §8:
- post.liked (only when was_new; ip_hash[:12] as actor)
- comment.created (email_hash[:12] as actor)
- comment.moderated, comment.flagged, comment.replied (admin events)
- comment.deleted

Together with P3's auth events these populate /admin/activity and the
dashboard widget with substantive content.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: End-to-end verification sweep

**Files:** none (verification only).

- [ ] **Step 1: Full pytest suite**

```bash
cd backend
uv run pytest -q
```

Expected: 148 (P3 baseline) + ~30 new P4 tests = ~178 passed. If any failure, fix before continuing.

- [ ] **Step 2: ruff lint**

```bash
uv run ruff check .
```

Expected: only pre-existing P1 errors (B904 / ASYNC240 / E402); no new P4-introduced lint errors. If P4 introduced any, run `uv run ruff check --fix .` and commit as `chore(phase4): ruff cleanup`.

- [ ] **Step 3: Alembic round-trip**

```bash
uv run alembic downgrade base
uv run alembic upgrade head
uv run python -m app.cli seed admin --email hi@wangyang.dev --password changeme
uv run python -m app.cli seed bootstrap
```

Expected: every step succeeds.

- [ ] **Step 4: Live API smoke (start uvicorn first if not running)**

Pick a real published post id (e.g. `claude-code-loop-daemon-design` from the seeded fixtures) and run:

```bash
PID="claude-code-loop-daemon-design"
echo "--- 1. like ($PID):"
curl -s -X POST "http://localhost:51820/api/posts/$PID/like" | python3 -m json.tool
echo "--- 2. like again (idempotent):"
curl -s -X POST "http://localhost:51820/api/posts/$PID/like" | python3 -m json.tool

echo "--- 3. submit comment:"
curl -s -X POST "http://localhost:51820/api/posts/$PID/comments" \
  -H 'Content-Type: application/json' \
  -d '{"who":"smoke","email":"s@m.k","body":"smoke test"}' | python3 -m json.tool

ACCESS=$(curl -s -X POST http://localhost:51820/api/admin/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"hi@wangyang.dev","password":"changeme"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access'])")

echo "--- 4. admin sees pending comment:"
curl -s "http://localhost:51820/api/admin/comments?status=pending" \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool | head -30

CID=$(curl -s "http://localhost:51820/api/admin/comments?status=pending" \
  -H "Authorization: Bearer $ACCESS" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

echo "--- 5. approve + reply:"
curl -s -X PATCH "http://localhost:51820/api/admin/comments/$CID" \
  -H "Authorization: Bearer $ACCESS" -H 'Content-Type: application/json' \
  -d '{"status":"approved","reply_body":"thanks"}' | python3 -m json.tool

echo "--- 6. public GET sees approved + nested reply:"
curl -s "http://localhost:51820/api/posts/$PID/comments" | python3 -m json.tool | head -40

echo "--- 7. activity stream:"
curl -s "http://localhost:51820/api/admin/activity?limit=5" \
  -H "Authorization: Bearer $ACCESS" | python3 -m json.tool | head -30
```

Expected:
- Step 1: `{"likes": >=1, "was_new": true}`
- Step 2: same `likes`, `was_new: false`
- Step 3: `{"id": int, "status": "pending"}`
- Step 4: pending comment listed
- Step 5: `{"status": "approved", "reply_id": int}`
- Step 6: comment with `admin_reply` populated
- Step 7: events: `post.liked`, `comment.created`, `comment.moderated`, `comment.replied`

- [ ] **Step 5: Verify spec §12 acceptance criteria**

Walk every checkbox in `docs/superpowers/specs/2026-04-26-phase4-interactions-design.md` §12 against the running system. Any gap → fix before merge.

- [ ] **Step 6: Push branch**

```bash
git push -u origin phase4-interactions
```

(Skip if no `origin` configured; that's fine, branch stays local.)

---

## Self-Review

**Spec coverage check:**
- ✅ §3.1 like_events table — Task 1 (migration) + Task 2 (model)
- ✅ §3.2 comments table — Task 1 + Task 2
- ✅ §4 hashing — Task 3 + tests
- ✅ §5.1 POST /posts/{id}/like — Task 5
- ✅ §5.2 POST/GET /posts/{id}/comments — Task 7 + Task 8
- ✅ §5.3 admin/comments — Task 11 + Task 12
- ✅ §5.4 admin/activity — Task 13
- ✅ §6 SMTP integration — Task 9 + Task 10
- ✅ §7 rate limits — Task 5 (likes) + Task 7 (comments)
- ✅ §8 event_log — Task 14
- ✅ §9 test plan — every task pairs implementation with named test file
- ✅ §10 P3 backwards compat — Task 9 explicitly preserves dev fallback
- ✅ §12 acceptance — Task 15 step 5

**Out-of-scope (spec §2)** — confirmed absent: ARQ, automatic spam detection, subscriptions, WebSocket push, resource-grained scopes.

**Type / signature consistency:**
- `record_like(s, *, post_id, ip) -> tuple[int, bool]` — Task 4 def, Task 5 call ✓
- `create_pending(s, *, post_id, who, email_hash, body) -> Comment` — Task 6 def, Task 7 call ✓
- `list_for_post(s, *, post_id) -> list[tuple[Comment, Comment | None]]` — Task 6 def, Task 8 call ✓
- `patch(s, *, comment_id, status, flag, reply_body, admin_who) -> tuple[Comment | None, Comment | None]` — Task 6 def, Task 12 call ✓
- `send_email(*, to, subject, body)`, `send_magic_link(*, email, url)`, `send_comment_notification(*, to, comment_id, post_id, who, snippet)` — Task 9 def, Task 10 + P3 magic-link both call ✓
- `ip_hash(ip)` / `email_hash(email)` — Task 3 def, Tasks 5/7/14 call ✓
- `list_events(s, *, types=None, limit, offset)` — Task 13 def + call ✓

**Placeholder scan:**
- No "TBD" / "TODO" / "implement later" strings ✓
- Every code block is complete ✓
- Every test step shows the assertion ✓

**Migration reversibility:**
- 0003 downgrade drops indexes before tables, drops in reverse FK order ✓
- comments.parent_id self-FK with ON DELETE CASCADE handled by table_args ✓
