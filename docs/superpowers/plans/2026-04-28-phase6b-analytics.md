# Phase 6b — Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture cookie-less SPA page-view beacons, aggregate them nightly into daily summaries, and expose four admin endpoints (dashboard KPI bundle + analytics summary + per-post + per-tag) that drive the prototype's admin console screens.

**Architecture:** Two tables — `hit_events` (raw, BIGSERIAL, 30-day retention) + `hit_daily` (composite-PK aggregate, JSONB top-10s, indefinite retention). Public `POST /api/hit` records via `hits` service which dedup-filters in Redis and bot-filters by UA before INSERT. ARQ cron at 03:00 UTC runs `analytics_rollup_task` to roll yesterday's events into hit_daily and truncate raw events older than 30 days. Admin reads merge "today from hit_events" + "history from hit_daily" so dashboards never lag.

**Tech Stack:** FastAPI 0.115+, async SQLAlchemy 2.0, Alembic, Postgres 16, Redis (existing), ARQ 0.x (existing), Pydantic v2.

---

## File Map

**Create**
- `backend/alembic/versions/0006_analytics.py`
- `backend/app/models/hit_event.py`
- `backend/app/models/hit_daily.py`
- `backend/app/schemas/analytics.py`
- `backend/app/services/hits.py`
- `backend/app/services/analytics.py`
- `backend/app/workers/tasks/analytics.py`
- `backend/app/routers/public/hits.py`
- `backend/app/routers/admin/analytics.py`
- `backend/tests/test_hits_service.py`
- `backend/tests/test_analytics_service.py`
- `backend/tests/test_public_hits.py`
- `backend/tests/test_admin_analytics.py`
- `backend/tests/test_analytics_rollup.py`
- `backend/tests/test_alembic_0006_roundtrip.py`

**Modify**
- `backend/app/models/__init__.py` — register `HitEvent`, `HitDaily`
- `backend/app/workers/tasks/__init__.py` — re-export `analytics_rollup`
- `backend/app/workers/runner.py` — register task + add cron job
- `backend/app/routers/public/__init__.py` — include hits router
- `backend/app/routers/admin/__init__.py` — include analytics router
- `backend/tests/conftest.py` — register `analytics_rollup` in ARQ inline mode

---

## Task 1: Migration 0006_analytics

**Files:**
- Create: `backend/alembic/versions/0006_analytics.py`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/0006_analytics.py`:

```python
"""analytics

Revision ID: 0006_analytics
Revises: 0005_media

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_analytics"
down_revision: str | None = "0005_media"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hit_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("referrer", sa.String(length=512), nullable=True),
        sa.Column("country", sa.CHAR(length=2), nullable=True),
        sa.Column("post_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hit_events_created_at",
        "hit_events",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_hit_events_post_id",
        "hit_events",
        ["post_id"],
        postgresql_where=sa.text("post_id IS NOT NULL"),
    )

    op.create_table(
        "hit_daily",
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.String(length=64), nullable=True),
        sa.Column(
            "referrers_top",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "countries_top",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["post_id"], ["posts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("date", "path"),
    )
    op.create_index(
        "ix_hit_daily_date",
        "hit_daily",
        [sa.text("date DESC")],
    )
    op.create_index(
        "ix_hit_daily_post_id",
        "hit_daily",
        ["post_id"],
        postgresql_where=sa.text("post_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_hit_daily_post_id", table_name="hit_daily")
    op.drop_index("ix_hit_daily_date", table_name="hit_daily")
    op.drop_table("hit_daily")
    op.drop_index("ix_hit_events_post_id", table_name="hit_events")
    op.drop_index("ix_hit_events_created_at", table_name="hit_events")
    op.drop_table("hit_events")
```

- [ ] **Step 2: Apply forward**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run alembic upgrade head
```

Expected: `Running upgrade 0005_media -> 0006_analytics, analytics`. No errors.

- [ ] **Step 3: Verify schema**

```bash
docker exec backend-postgres-1 psql -U myblog -d myblog -c "\d hit_events" 2>&1 | head -15
docker exec backend-postgres-1 psql -U myblog -d myblog -c "\d hit_daily" 2>&1 | head -15
```

Expected: `hit_events` has 6 columns (id BIGINT, path, referrer, country CHAR(2), post_id, created_at). `hit_daily` has 6 columns (date, path, hits, post_id, referrers_top jsonb, countries_top jsonb) + composite PK.

- [ ] **Step 4: Round-trip down/up**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run alembic downgrade 0005_media && uv run alembic upgrade head
```

Expected: clean down then up.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add alembic/versions/0006_analytics.py
git commit -m "feat(phase6b): 0006 migration (hit_events + hit_daily)"
```

---

## Task 2: ORM models — HitEvent + HitDaily

**Files:**
- Create: `backend/app/models/hit_event.py`
- Create: `backend/app/models/hit_daily.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write HitEvent**

Create `backend/app/models/hit_event.py`:

```python
from datetime import datetime

from sqlalchemy import CHAR, BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HitEvent(Base):
    __tablename__ = "hit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    referrer: Mapped[str | None] = mapped_column(String(512))
    country: Mapped[str | None] = mapped_column(CHAR(2))
    post_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("posts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
```

- [ ] **Step 2: Write HitDaily**

Create `backend/app/models/hit_daily.py`:

```python
from datetime import date as date_type

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HitDaily(Base):
    __tablename__ = "hit_daily"

    date: Mapped[date_type] = mapped_column(Date, primary_key=True)
    path: Mapped[str] = mapped_column(String(512), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, nullable=False)
    post_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("posts.id", ondelete="SET NULL")
    )
    referrers_top: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    countries_top: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
```

- [ ] **Step 3: Register in models/__init__.py**

In `backend/app/models/__init__.py`, add the imports + exports.

After `from app.models.event_log import EventLog`, add:

```python
from app.models.hit_daily import HitDaily
from app.models.hit_event import HitEvent
```

In `__all__`, add `"HitDaily", "HitEvent",` between `"EventLog"` and `"Integration"`.

- [ ] **Step 4: Verify import**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run python -c "from app.models import HitEvent, HitDaily; print(HitEvent.__tablename__, HitDaily.__tablename__)"
```

Expected: `hit_events hit_daily`

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/models/hit_event.py app/models/hit_daily.py app/models/__init__.py
git commit -m "feat(phase6b): ORM models for HitEvent + HitDaily"
```

---

## Task 3: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/analytics.py`

- [ ] **Step 1: Write schemas**

Create `backend/app/schemas/analytics.py`:

```python
"""Pydantic schemas for the analytics admin + public APIs."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


# --- public hit beacon ---


class HitRequest(BaseModel):
    path: str = Field(max_length=512)
    referrer: str | None = Field(default=None, max_length=512)
    post_id: str | None = Field(default=None, max_length=64)


# --- dashboard KPIs ---


class HitsKPI(BaseModel):
    today: int
    last_7d: int
    last_30d: int


class LikesKPI(BaseModel):
    total: int
    last_7d: int


class CommentsKPI(BaseModel):
    total: int
    pending: int


class PostsKPI(BaseModel):
    published: int
    draft: int
    scheduled: int


class MediaKPI(BaseModel):
    count: int


class DashboardResponse(BaseModel):
    hits: HitsKPI
    likes: LikesKPI
    comments: CommentsKPI
    posts: PostsKPI
    media: MediaKPI


# --- analytics bundle ---


class DayPoint(BaseModel):
    date: date
    hits: int


class PathHits(BaseModel):
    path: str
    hits: int


class ReferrerHits(BaseModel):
    referrer: str
    hits: int


class CountryHits(BaseModel):
    country: str
    hits: int


class AnalyticsBundleResponse(BaseModel):
    timeseries: list[DayPoint]
    top_paths: list[PathHits]
    top_referrers: list[ReferrerHits]
    top_countries: list[CountryHits]


# --- per-post + per-tag ---


class PostHitsItem(BaseModel):
    post_id: str
    title: str
    hits: int


class TagHitsItem(BaseModel):
    tag_id: int
    slug: str
    name: str
    hits: int
```

- [ ] **Step 2: Verify import**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run python -c "from app.schemas.analytics import HitRequest, DashboardResponse, AnalyticsBundleResponse, PostHitsItem, TagHitsItem; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/schemas/analytics.py
git commit -m "feat(phase6b): Pydantic schemas for analytics"
```

---

## Task 4: hits service (write path) — TDD

**Files:**
- Create: `backend/app/services/hits.py`
- Create: `backend/tests/test_hits_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_hits_service.py`:

```python
"""hits service unit tests."""
from __future__ import annotations

from datetime import UTC, datetime

import fakeredis.aioredis
import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import HitEvent, Post
from app.services import hits as hits_svc


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
async def cleanup_hits():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.commit()


async def _seed_post(s, *, slug="howdy") -> str:
    from app.models import Tag
    tag = (await s.execute(Tag.__table__.select().limit(1))).first()
    if tag is None:
        s.add(Tag(slug="general", name="General", color="#888", sort_order=0))
        await s.flush()
        tag = (await s.execute(Tag.__table__.select().limit(1))).first()
    row = Post(
        id=slug, n=1, title="Howdy", subtitle="", date="2026-04-28",
        read=1, lang="en", summary="", tldr="", body_md="", body_json={},
        word_count=0, status="published", featured=False, private=False,
        comments_enabled=True, tag_id=tag.id,
    )
    s.add(row)
    await s.flush()
    return slug


async def test_record_happy_path(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country="US", user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].country == "US"


async def test_record_drops_bot_user_agent(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="GoogleBot/2.1 (compatible)", post_id=None,
        )
        await s.commit()
    assert ok is False
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows == []


async def test_record_dedups_same_ip_path_in_60s(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok1 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        ok2 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok1 is True
    assert ok2 is False
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1


async def test_record_different_paths_same_ip_both_pass(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok1 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        ok2 = await hits_svc.record(
            s, redis=redis, path="/about", referrer=None, ip="1.2.3.4",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok1 is True and ok2 is True


async def test_record_unknown_post_id_falls_back_to_null(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/post/nonexistent", referrer=None,
            ip="1.2.3.4", country=None, user_agent="Mozilla/5.0",
            post_id="nonexistent",
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].post_id is None


async def test_record_known_post_id_persists(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        slug = await _seed_post(s, slug="hits-test-post")
        await s.commit()
    try:
        async with AsyncSessionLocal() as s:
            ok = await hits_svc.record(
                s, redis=redis, path="/post/hits-test-post", referrer=None,
                ip="1.2.3.4", country=None, user_agent="Mozilla/5.0",
                post_id=slug,
            )
            await s.commit()
        assert ok is True
        async with AsyncSessionLocal() as s:
            rows = (await s.execute(select(HitEvent))).scalars().all()
        assert len(rows) == 1
        assert rows[0].post_id == slug
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Post).where(Post.id == slug))
            await s.commit()


async def test_record_lowercase_country_becomes_null(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="1.2.3.4",
            country="us", user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows[0].country is None


@pytest.mark.parametrize("bad", ["USA", "u1", "1A", "", "U"])
async def test_record_non_iso_country_becomes_null(redis, cleanup_hits, bad):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path=f"/?{bad}", referrer=None, ip="1.2.3.4",
            country=bad, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent).where(HitEvent.path == f"/?{bad}"))).scalars().all()
    assert rows[0].country is None


async def test_record_empty_ip_does_not_crash(redis, cleanup_hits):
    async with AsyncSessionLocal() as s:
        ok = await hits_svc.record(
            s, redis=redis, path="/empty-ip", referrer=None, ip="",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok is True


async def test_record_after_dedup_expiry(redis, cleanup_hits):
    """Manually expire the dedup key to simulate 61s elapsed."""
    async with AsyncSessionLocal() as s:
        ok1 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="9.9.9.9",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()

    # Drop all dedup keys to simulate TTL expiry.
    async for k in redis.scan_iter("hit:*"):
        await redis.delete(k)

    async with AsyncSessionLocal() as s:
        ok2 = await hits_svc.record(
            s, redis=redis, path="/", referrer=None, ip="9.9.9.9",
            country=None, user_agent="Mozilla/5.0", post_id=None,
        )
        await s.commit()
    assert ok1 is True and ok2 is True
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_hits_service.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.hits'`.

- [ ] **Step 3: Implement hits service**

Create `backend/app/services/hits.py`:

```python
"""Hit beacon write path: filter (UA bot, Redis dedup) + INSERT."""
from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HitEvent, Post

BOT_RE = re.compile(
    r"(bot|crawler|spider|curl|wget|httpclient|python-requests)", re.I
)
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
_DEDUP_TTL = 60  # seconds


def _bot(ua: str | None) -> bool:
    return bool(ua and BOT_RE.search(ua))


def _normalize_country(country: str | None) -> str | None:
    if country is None:
        return None
    return country if _COUNTRY_RE.match(country) else None


def _dedup_key(ip: str, path: str) -> str:
    h = hashlib.sha256(f"{ip}|{path}".encode()).hexdigest()[:16]
    return f"hit:{h}"


async def _post_exists(s: AsyncSession, post_id: str) -> bool:
    exists = await s.execute(select(Post.id).where(Post.id == post_id))
    return exists.scalar_one_or_none() is not None


async def record(
    s: AsyncSession,
    *,
    redis,
    path: str,
    referrer: str | None,
    ip: str,
    country: str | None,
    user_agent: str | None,
    post_id: str | None,
) -> bool:
    """Persist one hit. Returns True if recorded, False if filtered.

    Filters in order: UA bot regex → Redis 60s dedup on hash(ip|path).
    Validates post_id (NULL if not in posts table) and country (NULL if not 2-letter ASCII upper).
    Never writes IP / UA / raw user_agent to DB.
    """
    if _bot(user_agent):
        return False

    key = _dedup_key(ip, path)
    set_ok = await redis.set(key, "1", ex=_DEDUP_TTL, nx=True)
    if not set_ok:
        return False

    if post_id is not None and not await _post_exists(s, post_id):
        post_id = None

    s.add(HitEvent(
        path=path[:512],
        referrer=(referrer[:512] if referrer else None),
        country=_normalize_country(country),
        post_id=post_id,
        created_at=datetime.now(UTC),
    ))
    await s.flush()
    return True
```

- [ ] **Step 4: Run — expect 14 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_hits_service.py -x 2>&1 | tail -10
```

Expected: `14 passed` (10 named + 5 parametrized minus 1 named that's parametrized = ... let pytest count). Actual count: 5 parametrized values + 9 single-name tests = 14 cases.

If a test fails, debug and fix before committing.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/hits.py tests/test_hits_service.py
git commit -m "feat(phase6b): hits service (UA bot + Redis dedup + post_id/country validation)"
```

---

## Task 5: POST /api/hit (public beacon)

**Files:**
- Create: `backend/app/routers/public/hits.py`
- Modify: `backend/app/routers/public/__init__.py`
- Create: `backend/tests/test_public_hits.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_public_hits.py`:

```python
import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import HitEvent


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def cleanup_hits():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.commit()


async def test_post_hit_204(client, cleanup_hits):
    r = await client.post("/api/hit", json={"path": "/foo"})
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].path == "/foo"


async def test_post_hit_missing_path_422(client, cleanup_hits):
    r = await client.post("/api/hit", json={})
    assert r.status_code == 422


async def test_post_hit_dedup_returns_204_but_no_row(client, cleanup_hits):
    r1 = await client.post("/api/hit", json={"path": "/foo"})
    r2 = await client.post("/api/hit", json={"path": "/foo"})
    assert r1.status_code == 204 and r2.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1


async def test_post_hit_unknown_post_id(client, cleanup_hits):
    r = await client.post("/api/hit", json={"path": "/post/x", "post_id": "x"})
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert len(rows) == 1
    assert rows[0].post_id is None


async def test_post_hit_bot_user_agent(client, cleanup_hits):
    r = await client.post(
        "/api/hit",
        json={"path": "/foo"},
        headers={"User-Agent": "GoogleBot/2.1"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows == []


async def test_post_hit_cf_ipcountry_header(client, cleanup_hits):
    r = await client.post(
        "/api/hit",
        json={"path": "/foo"},
        headers={"CF-IPCountry": "JP"},
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(HitEvent))).scalars().all()
    assert rows[0].country == "JP"
```

- [ ] **Step 2: Run — expect 404 (route not registered)**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_public_hits.py -x 2>&1 | tail -10
```

Expected: tests fail with 404 status (route doesn't exist).

- [ ] **Step 3: Write the router**

Create `backend/app/routers/public/hits.py`:

```python
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.redis import get_redis
from app.schemas.analytics import HitRequest
from app.services import hits as hits_svc

router = APIRouter()


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "") or ""


@router.post("/hit", status_code=204)
async def record_hit(
    req: HitRequest,
    request: Request,
    s: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> Response:
    ip = _client_ip(request)
    country = (request.headers.get("CF-IPCountry") or "").upper() or None
    user_agent = request.headers.get("User-Agent")

    await hits_svc.record(
        s,
        redis=redis,
        path=req.path,
        referrer=req.referrer,
        ip=ip,
        country=country,
        user_agent=user_agent,
        post_id=req.post_id,
    )
    await s.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router**

In `backend/app/routers/public/__init__.py`, add the import (alphabetical):

```python
from app.routers.public.hits import router as hits_router
```

And below:

```python
router.include_router(hits_router, tags=["public"])
```

- [ ] **Step 5: Run — expect 6 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_public_hits.py -x 2>&1 | tail -10
```

Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/public/hits.py app/routers/public/__init__.py tests/test_public_hits.py
git commit -m "feat(phase6b): POST /api/hit beacon (cookie-less, always 204)"
```

---

## Task 6: ARQ analytics_rollup task + cron

**Files:**
- Create: `backend/app/workers/tasks/analytics.py`
- Modify: `backend/app/workers/tasks/__init__.py`
- Modify: `backend/app/workers/runner.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_analytics_rollup.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_analytics_rollup.py`:

```python
"""ARQ analytics_rollup task: rolls hit_events → hit_daily, truncates raw > 30d."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent
from app.workers.tasks.analytics import analytics_rollup


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def clean_analytics():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.execute(delete(HitDaily))
        await s.commit()


async def _seed_event(s, *, path, referrer=None, country=None, post_id=None, when):
    s.add(HitEvent(
        path=path, referrer=referrer, country=country, post_id=post_id,
        created_at=when,
    ))


async def test_rollup_aggregates_by_path(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    when = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=12)
    async with AsyncSessionLocal() as s:
        for _ in range(5):
            await _seed_event(s, path="/a", when=when)
        for _ in range(3):
            await _seed_event(s, path="/b", when=when)
        await s.commit()

    res = await analytics_rollup({}, target_date=yesterday.isoformat())
    assert res["paths_rolled"] == 2

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(HitDaily).where(HitDaily.date == yesterday)
        )).scalars().all()
    counts = {r.path: r.hits for r in rows}
    assert counts == {"/a": 5, "/b": 3}


async def test_rollup_referrers_and_countries_top(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    when = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=2)
    async with AsyncSessionLocal() as s:
        for _ in range(3):
            await _seed_event(s, path="/x", referrer="https://hn.example/", country="US", when=when)
        for _ in range(2):
            await _seed_event(s, path="/x", referrer="https://reddit.example/", country="JP", when=when)
        await _seed_event(s, path="/x", referrer=None, country=None, when=when)
        await s.commit()

    await analytics_rollup({}, target_date=yesterday.isoformat())

    async with AsyncSessionLocal() as s:
        row = (await s.execute(
            select(HitDaily).where(HitDaily.date == yesterday).where(HitDaily.path == "/x")
        )).scalar_one()
    assert row.hits == 6
    refs = {item["r"]: item["n"] for item in row.referrers_top}
    assert refs == {"https://hn.example/": 3, "https://reddit.example/": 2}
    countries = {item["c"]: item["n"] for item in row.countries_top}
    assert countries == {"US": 3, "JP": 2}


async def test_rollup_is_idempotent(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    when = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=4)
    async with AsyncSessionLocal() as s:
        for _ in range(2):
            await _seed_event(s, path="/y", when=when)
        await s.commit()

    await analytics_rollup({}, target_date=yesterday.isoformat())
    await analytics_rollup({}, target_date=yesterday.isoformat())

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            select(HitDaily).where(HitDaily.date == yesterday)
        )).scalars().all()
    assert len(rows) == 1
    assert rows[0].hits == 2


async def test_rollup_truncates_raw_older_than_30d(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    old = datetime.now(UTC) - timedelta(days=31)
    recent = datetime.combine(yesterday, datetime.min.time(), tzinfo=UTC) + timedelta(hours=1)
    async with AsyncSessionLocal() as s:
        await _seed_event(s, path="/old", when=old)
        await _seed_event(s, path="/new", when=recent)
        await s.commit()

    res = await analytics_rollup({}, target_date=yesterday.isoformat())
    assert res["rows_truncated"] >= 1

    async with AsyncSessionLocal() as s:
        remaining = (await s.execute(
            select(HitEvent).where(HitEvent.path == "/old")
        )).scalars().all()
    assert remaining == []


async def test_rollup_empty_day(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    res = await analytics_rollup({}, target_date=yesterday.isoformat())
    assert res["paths_rolled"] == 0
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_rollup.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.workers.tasks.analytics'`.

- [ ] **Step 3: Implement task**

Create `backend/app/workers/tasks/analytics.py`:

```python
"""ARQ analytics_rollup: hit_events → hit_daily, then prune raw > 30 days."""
from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent
from app.services.event_log import write_event


def _parse_date(s: str | None) -> date:
    if s is None:
        return (datetime.now(UTC) - timedelta(days=1)).date()
    return date.fromisoformat(s)


async def analytics_rollup(ctx: dict, target_date: str | None = None) -> dict:
    """Roll one UTC day of hit_events into hit_daily, then truncate raw > 30 days.

    Idempotent: re-running for the same target_date overwrites the
    (date, path) rows in hit_daily.
    """
    d = _parse_date(target_date)
    start = datetime.combine(d, datetime.min.time(), tzinfo=UTC)
    end = start + timedelta(days=1)

    paths_rolled = 0
    try:
        async with AsyncSessionLocal() as s:
            # Group by path: count + a representative post_id (MIN if any).
            grouped = await s.execute(
                select(
                    HitEvent.path,
                    HitEvent.post_id,
                    HitEvent.referrer,
                    HitEvent.country,
                ).where(HitEvent.created_at >= start).where(HitEvent.created_at < end)
            )
            buckets: dict[str, dict] = {}
            for path, post_id, referrer, country in grouped.all():
                b = buckets.setdefault(path, {
                    "path": path,
                    "post_id": post_id,
                    "refs": Counter(),
                    "countries": Counter(),
                    "hits": 0,
                })
                b["hits"] += 1
                # Pick first non-NULL post_id seen.
                if b["post_id"] is None and post_id is not None:
                    b["post_id"] = post_id
                if referrer:
                    b["refs"][referrer] += 1
                if country:
                    b["countries"][country] += 1

            for path, b in buckets.items():
                top_refs = [
                    {"r": r, "n": n} for r, n in b["refs"].most_common(10)
                ]
                top_countries = [
                    {"c": c, "n": n} for c, n in b["countries"].most_common(10)
                ]
                stmt = pg_insert(HitDaily).values(
                    date=d, path=path, hits=b["hits"], post_id=b["post_id"],
                    referrers_top=top_refs, countries_top=top_countries,
                ).on_conflict_do_update(
                    index_elements=["date", "path"],
                    set_={
                        "hits": b["hits"],
                        "post_id": b["post_id"],
                        "referrers_top": top_refs,
                        "countries_top": top_countries,
                    },
                )
                await s.execute(stmt)
                paths_rolled += 1

            cutoff = datetime.now(UTC) - timedelta(days=30)
            res = await s.execute(delete(HitEvent).where(HitEvent.created_at < cutoff))
            rows_truncated = res.rowcount or 0

            await write_event(
                s, type="analytics.rollup", actor="system",
                target=d.isoformat(),
                meta={
                    "date": d.isoformat(),
                    "paths_rolled": paths_rolled,
                    "rows_truncated": rows_truncated,
                },
            )
            await s.commit()
    except Exception as e:
        async with AsyncSessionLocal() as s2:
            await write_event(
                s2, type="analytics.rollup_failed", actor="system",
                target=d.isoformat(),
                meta={"date": d.isoformat(), "error": str(e)},
            )
            await s2.commit()
        raise

    return {
        "date": d.isoformat(),
        "paths_rolled": paths_rolled,
        "rows_truncated": rows_truncated,
    }
```

- [ ] **Step 4: Re-export in tasks/__init__.py**

In `backend/app/workers/tasks/__init__.py`, add the import + export.

After the existing imports, add:

```python
from app.workers.tasks.analytics import analytics_rollup
```

In `__all__`, add `"analytics_rollup",` (alphabetically first).

- [ ] **Step 5: Register task + cron in runner.py**

In `backend/app/workers/runner.py`:

After `q.register("sync_github_contrib", t.sync_github_contrib)`, add:

```python
q.register("analytics_rollup", t.analytics_rollup)
```

In `WorkerSettings.functions`, append `t.analytics_rollup,`.

In `WorkerSettings.cron_jobs`, append:

```python
        cron(t.analytics_rollup, hour={3}, minute={0}),  # 03:00 UTC daily
```

(The existing `prune_event_log` uses `hour={3}, minute={0}` — both run at the same time, which is fine.)

- [ ] **Step 6: Register in test conftest**

In `backend/tests/conftest.py`, in the `_register_arq_tasks` fixture, add the line:

```python
    q.register("analytics_rollup", t.analytics_rollup)
```

right after `q.register("send_email_task", t.send_email_task)`.

- [ ] **Step 7: Run — expect 5 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_rollup.py -x 2>&1 | tail -10
```

Expected: `5 passed`.

- [ ] **Step 8: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/workers/tasks/analytics.py app/workers/tasks/__init__.py app/workers/runner.py tests/conftest.py tests/test_analytics_rollup.py
git commit -m "feat(phase6b): analytics_rollup ARQ task (03:00 UTC cron, 30d truncate)"
```

---

## Task 7: analytics service — dashboard_kpis + timeseries

**Files:**
- Create: `backend/app/services/analytics.py`
- Create: `backend/tests/test_analytics_service.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_analytics_service.py`:

```python
"""analytics service unit tests (read path)."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent
from app.services import analytics


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def clean_analytics():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.execute(delete(HitDaily))
        await s.commit()


async def test_timeseries_pads_zero_days(clean_analytics):
    async with AsyncSessionLocal() as s:
        result = await analytics.timeseries(s, days=7)
    assert len(result) == 7
    assert all(p.hits == 0 for p in result)


async def test_timeseries_today_from_hit_events(clean_analytics):
    """today's hits live in hit_events, not hit_daily — pre-rollup."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        for _ in range(4):
            s.add(HitEvent(path="/a", created_at=now))
        await s.commit()

    async with AsyncSessionLocal() as s:
        result = await analytics.timeseries(s, days=3)
    today_point = result[-1]
    assert today_point.hits == 4


async def test_timeseries_history_from_hit_daily(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/x", hits=12, post_id=None,
                       referrers_top=[], countries_top=[]))
        s.add(HitDaily(date=yesterday, path="/y", hits=8, post_id=None,
                       referrers_top=[], countries_top=[]))
        await s.commit()

    async with AsyncSessionLocal() as s:
        result = await analytics.timeseries(s, days=3)
    yesterday_point = next(p for p in result if p.date == yesterday)
    assert yesterday_point.hits == 20


async def test_dashboard_kpis_empty(clean_analytics):
    async with AsyncSessionLocal() as s:
        kpi = await analytics.dashboard_kpis(s)
    assert kpi.hits.today == 0
    assert kpi.hits.last_7d == 0
    assert kpi.hits.last_30d == 0


async def test_dashboard_kpis_today_count(clean_analytics):
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        for _ in range(3):
            s.add(HitEvent(path="/", created_at=now))
        await s.commit()
    async with AsyncSessionLocal() as s:
        kpi = await analytics.dashboard_kpis(s)
    assert kpi.hits.today == 3
    assert kpi.hits.last_7d == 3
    assert kpi.hits.last_30d == 3
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_service.py -x 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'app.services.analytics'`.

- [ ] **Step 3: Implement service (partial — KPIs + timeseries)**

Create `backend/app/services/analytics.py`:

```python
"""Analytics read service. Today's hits come from hit_events (live);
historical days come from hit_daily."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Comment,
    HitDaily,
    HitEvent,
    LikeEvent,
    Media,
    Post,
)
from app.schemas.analytics import (
    CommentsKPI,
    CountryHits,
    DashboardResponse,
    DayPoint,
    HitsKPI,
    LikesKPI,
    MediaKPI,
    PathHits,
    PostHitsItem,
    PostsKPI,
    ReferrerHits,
    TagHitsItem,
)


def _today_utc() -> date:
    return datetime.now(UTC).date()


def _today_start_utc() -> datetime:
    return datetime.combine(_today_utc(), datetime.min.time(), tzinfo=UTC)


async def _hits_today(s: AsyncSession) -> int:
    res = await s.execute(
        select(func.count(HitEvent.id)).where(HitEvent.created_at >= _today_start_utc())
    )
    return int(res.scalar() or 0)


async def _hits_history(s: AsyncSession, *, days: int) -> dict[date, int]:
    """Sum hit_daily.hits per date for last `days` excluding today."""
    today = _today_utc()
    start = today - timedelta(days=days - 1)
    end_exclusive = today  # everything before today
    res = await s.execute(
        select(HitDaily.date, func.sum(HitDaily.hits))
        .where(HitDaily.date >= start)
        .where(HitDaily.date < end_exclusive)
        .group_by(HitDaily.date)
    )
    return {row[0]: int(row[1] or 0) for row in res.all()}


async def timeseries(s: AsyncSession, *, days: int) -> list[DayPoint]:
    today = _today_utc()
    history = await _hits_history(s, days=days)
    today_hits = await _hits_today(s)

    points: list[DayPoint] = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        n = today_hits if d == today else history.get(d, 0)
        points.append(DayPoint(date=d, hits=n))
    return points


async def dashboard_kpis(s: AsyncSession) -> DashboardResponse:
    # hits — today live + last_7d/last_30d sums
    today = _today_utc()
    today_hits = await _hits_today(s)

    async def _sum_history(days: int) -> int:
        start = today - timedelta(days=days - 1)
        end_exclusive = today
        res = await s.execute(
            select(func.coalesce(func.sum(HitDaily.hits), 0))
            .where(HitDaily.date >= start)
            .where(HitDaily.date < end_exclusive)
        )
        return int(res.scalar() or 0)

    last_7d = today_hits + await _sum_history(7)
    last_30d = today_hits + await _sum_history(30)

    # likes
    likes_total = int((await s.execute(select(func.count(LikeEvent.id)))).scalar() or 0)
    seven_ago = today - timedelta(days=7)
    likes_7 = int((await s.execute(
        select(func.count(LikeEvent.id)).where(LikeEvent.day >= seven_ago)
    )).scalar() or 0)

    # comments
    comments_total = int((await s.execute(select(func.count(Comment.id)))).scalar() or 0)
    comments_pending = int((await s.execute(
        select(func.count(Comment.id)).where(Comment.status == "pending")
    )).scalar() or 0)

    # posts
    async def _count_posts(status: str) -> int:
        return int((await s.execute(
            select(func.count(Post.id)).where(Post.status == status)
        )).scalar() or 0)

    posts_published = await _count_posts("published")
    posts_draft = await _count_posts("draft")
    posts_scheduled = await _count_posts("scheduled")

    # media
    media_count = int((await s.execute(select(func.count(Media.id)))).scalar() or 0)

    return DashboardResponse(
        hits=HitsKPI(today=today_hits, last_7d=last_7d, last_30d=last_30d),
        likes=LikesKPI(total=likes_total, last_7d=likes_7),
        comments=CommentsKPI(total=comments_total, pending=comments_pending),
        posts=PostsKPI(
            published=posts_published, draft=posts_draft, scheduled=posts_scheduled
        ),
        media=MediaKPI(count=media_count),
    )
```

- [ ] **Step 4: Run — expect 5 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_service.py -x 2>&1 | tail -10
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/analytics.py tests/test_analytics_service.py
git commit -m "feat(phase6b): analytics service — dashboard_kpis + timeseries"
```

---

## Task 8: analytics service — top_paths / top_referrers / top_countries

**Files:**
- Modify: `backend/app/services/analytics.py`
- Modify: `backend/tests/test_analytics_service.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_analytics_service.py`:

```python
async def test_top_paths_orders_desc(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/big", hits=50,
                       referrers_top=[], countries_top=[]))
        s.add(HitDaily(date=yesterday, path="/small", hits=2,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.top_paths(s, days=7, limit=5)
    assert [p.path for p in result] == ["/big", "/small"]
    assert result[0].hits == 50


async def test_top_referrers_merges_jsonb(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    two_ago = yesterday - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/a", hits=10,
                       referrers_top=[{"r": "https://hn", "n": 6}, {"r": "https://r", "n": 4}],
                       countries_top=[]))
        s.add(HitDaily(date=two_ago, path="/a", hits=8,
                       referrers_top=[{"r": "https://hn", "n": 5}, {"r": "https://t", "n": 3}],
                       countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.top_referrers(s, days=7, limit=10)
    by_ref = {p.referrer: p.hits for p in result}
    assert by_ref["https://hn"] == 11
    assert by_ref["https://r"] == 4
    assert by_ref["https://t"] == 3


async def test_top_countries_excludes_null(clean_analytics):
    """countries_top JSON only contains non-NULL countries — confirm
    that NULL country events from today don't appear."""
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as s:
        s.add(HitEvent(path="/", country="US", created_at=now))
        s.add(HitEvent(path="/", country="US", created_at=now))
        s.add(HitEvent(path="/", country=None, created_at=now))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.top_countries(s, days=7, limit=10)
    assert len(result) == 1
    assert result[0].country == "US"
    assert result[0].hits == 2
```

- [ ] **Step 2: Run — expect AttributeError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_service.py -k "top_" -x 2>&1 | tail -10
```

Expected: `AttributeError: module 'app.services.analytics' has no attribute 'top_paths'`.

- [ ] **Step 3: Implement top_* helpers**

Append to `backend/app/services/analytics.py`:

```python
async def top_paths(
    s: AsyncSession, *, days: int, limit: int = 10
) -> list[PathHits]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)
    today_start_dt = _today_start_utc()

    # Historical days from hit_daily.
    history = await s.execute(
        select(HitDaily.path, func.sum(HitDaily.hits).label("h"))
        .where(HitDaily.date >= start).where(HitDaily.date < today)
        .group_by(HitDaily.path)
    )
    counts: dict[str, int] = {p: int(h or 0) for p, h in history.all()}

    # Today's contribution from hit_events.
    today_rows = await s.execute(
        select(HitEvent.path, func.count(HitEvent.id))
        .where(HitEvent.created_at >= today_start_dt)
        .group_by(HitEvent.path)
    )
    for p, n in today_rows.all():
        counts[p] = counts.get(p, 0) + int(n or 0)

    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [PathHits(path=p, hits=n) for p, n in sorted_pairs]


async def _merge_jsonb_top(
    s: AsyncSession, *, column, key: str, days: int
) -> dict[str, int]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)
    res = await s.execute(
        select(column).where(HitDaily.date >= start).where(HitDaily.date < today)
    )
    counts: dict[str, int] = {}
    for (arr,) in res.all():
        if not arr:
            continue
        for item in arr:
            counts[item[key]] = counts.get(item[key], 0) + int(item["n"])
    return counts


async def top_referrers(
    s: AsyncSession, *, days: int, limit: int = 10
) -> list[ReferrerHits]:
    counts = await _merge_jsonb_top(
        s, column=HitDaily.referrers_top, key="r", days=days
    )
    # Today's contribution from hit_events.
    today_rows = await s.execute(
        select(HitEvent.referrer, func.count(HitEvent.id))
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.referrer.isnot(None))
        .group_by(HitEvent.referrer)
    )
    for r, n in today_rows.all():
        counts[r] = counts.get(r, 0) + int(n or 0)
    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [ReferrerHits(referrer=r, hits=n) for r, n in sorted_pairs]


async def top_countries(
    s: AsyncSession, *, days: int, limit: int = 10
) -> list[CountryHits]:
    counts = await _merge_jsonb_top(
        s, column=HitDaily.countries_top, key="c", days=days
    )
    today_rows = await s.execute(
        select(HitEvent.country, func.count(HitEvent.id))
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.country.isnot(None))
        .group_by(HitEvent.country)
    )
    for c, n in today_rows.all():
        counts[c] = counts.get(c, 0) + int(n or 0)
    sorted_pairs = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [CountryHits(country=c, hits=n) for c, n in sorted_pairs]
```

- [ ] **Step 4: Run — expect 8 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_service.py -x 2>&1 | tail -10
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/analytics.py tests/test_analytics_service.py
git commit -m "feat(phase6b): analytics service — top_paths/top_referrers/top_countries"
```

---

## Task 9: analytics service — per_post + per_tag

**Files:**
- Modify: `backend/app/services/analytics.py`
- Modify: `backend/tests/test_analytics_service.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_analytics_service.py`:

```python
from app.models import Post, Tag


async def _seed_post_with_tag(s, *, slug, tag_slug="general", title="Untitled"):
    tag = (await s.execute(
        Tag.__table__.select().where(Tag.slug == tag_slug)
    )).first()
    if tag is None:
        s.add(Tag(slug=tag_slug, name=tag_slug.title(), color="#888", sort_order=0))
        await s.flush()
        tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == tag_slug)
        )).first()
    s.add(Post(
        id=slug, n=1, title=title, subtitle="", date="2026-04-28",
        read=1, lang="en", summary="", tldr="", body_md="", body_json={},
        word_count=0, status="published", featured=False, private=False,
        comments_enabled=True, tag_id=tag.id,
    ))
    await s.flush()
    return slug


@pytest.fixture
async def clean_posts_tags():
    yield
    async with AsyncSessionLocal() as s:
        from sqlalchemy import delete as sa_delete
        await s.execute(sa_delete(Post).where(Post.id.like("p6btest-%")))
        await s.execute(sa_delete(Tag).where(Tag.slug == "p6btest-tag"))
        await s.commit()


async def test_per_post_groups_by_post_id(clean_analytics, clean_posts_tags):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        slug = await _seed_post_with_tag(
            s, slug="p6btest-howdy", tag_slug="p6btest-tag", title="Howdy"
        )
        s.add(HitDaily(date=yesterday, path="/post/p6btest-howdy",
                       hits=10, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.per_post(s, days=7)
    titles = {r.post_id: r.title for r in result}
    assert "p6btest-howdy" in titles
    assert titles["p6btest-howdy"] == "Howdy"


async def test_per_post_excludes_null_post_id(clean_analytics):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        s.add(HitDaily(date=yesterday, path="/", hits=99, post_id=None,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.per_post(s, days=7)
    assert all(r.hits != 99 for r in result)


async def test_per_tag_joins_to_tags(clean_analytics, clean_posts_tags):
    yesterday = date.today() - timedelta(days=1)
    async with AsyncSessionLocal() as s:
        slug = await _seed_post_with_tag(
            s, slug="p6btest-tagjoin", tag_slug="p6btest-tag", title="Tag Join"
        )
        s.add(HitDaily(date=yesterday, path="/post/p6btest-tagjoin",
                       hits=7, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    async with AsyncSessionLocal() as s:
        result = await analytics.per_tag(s, days=7)
    by_slug = {t.slug: t.hits for t in result}
    assert by_slug.get("p6btest-tag", 0) >= 7
```

- [ ] **Step 2: Run — expect AttributeError**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_service.py -k "per_" -x 2>&1 | tail -10
```

Expected: `AttributeError: module 'app.services.analytics' has no attribute 'per_post'`.

- [ ] **Step 3: Implement per_post + per_tag**

Append to `backend/app/services/analytics.py` (and update imports at top to add `Tag`):

In the imports at the top of `app/services/analytics.py`, replace:

```python
from app.models import (
    Comment,
    HitDaily,
    HitEvent,
    LikeEvent,
    Media,
    Post,
)
```

with:

```python
from app.models import (
    Comment,
    HitDaily,
    HitEvent,
    LikeEvent,
    Media,
    Post,
    Tag,
)
```

Append at the bottom of the file:

```python
async def per_post(
    s: AsyncSession, *, days: int, limit: int = 50
) -> list[PostHitsItem]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    # Historical sums from hit_daily, JOIN posts for title.
    history = await s.execute(
        select(
            HitDaily.post_id, Post.title, func.sum(HitDaily.hits).label("h"),
        )
        .join(Post, Post.id == HitDaily.post_id)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < today)
        .where(HitDaily.post_id.isnot(None))
        .group_by(HitDaily.post_id, Post.title)
    )
    counts: dict[str, tuple[str, int]] = {}
    for post_id, title, h in history.all():
        counts[post_id] = (title, int(h or 0))

    # Today's contribution from hit_events with post_id.
    today_rows = await s.execute(
        select(HitEvent.post_id, Post.title, func.count(HitEvent.id))
        .join(Post, Post.id == HitEvent.post_id)
        .where(HitEvent.created_at >= _today_start_utc())
        .where(HitEvent.post_id.isnot(None))
        .group_by(HitEvent.post_id, Post.title)
    )
    for post_id, title, n in today_rows.all():
        prev_title, prev = counts.get(post_id, (title, 0))
        counts[post_id] = (prev_title, prev + int(n or 0))

    sorted_items = sorted(counts.items(), key=lambda kv: kv[1][1], reverse=True)[:limit]
    return [
        PostHitsItem(post_id=pid, title=title, hits=n)
        for pid, (title, n) in sorted_items
    ]


async def per_tag(s: AsyncSession, *, days: int) -> list[TagHitsItem]:
    today = _today_utc()
    start = today - timedelta(days=days - 1)

    history = await s.execute(
        select(
            Tag.id, Tag.slug, Tag.name, func.sum(HitDaily.hits).label("h"),
        )
        .join(Post, Post.id == HitDaily.post_id)
        .join(Tag, Tag.id == Post.tag_id)
        .where(HitDaily.date >= start)
        .where(HitDaily.date < today)
        .group_by(Tag.id, Tag.slug, Tag.name)
    )
    counts: dict[int, tuple[str, str, int]] = {}
    for tid, slug, name, h in history.all():
        counts[tid] = (slug, name, int(h or 0))

    today_rows = await s.execute(
        select(Tag.id, Tag.slug, Tag.name, func.count(HitEvent.id))
        .join(Post, Post.id == HitEvent.post_id)
        .join(Tag, Tag.id == Post.tag_id)
        .where(HitEvent.created_at >= _today_start_utc())
        .group_by(Tag.id, Tag.slug, Tag.name)
    )
    for tid, slug, name, n in today_rows.all():
        prev_slug, prev_name, prev = counts.get(tid, (slug, name, 0))
        counts[tid] = (prev_slug, prev_name, prev + int(n or 0))

    sorted_items = sorted(counts.items(), key=lambda kv: kv[1][2], reverse=True)
    return [
        TagHitsItem(tag_id=tid, slug=s_, name=n_, hits=h_)
        for tid, (s_, n_, h_) in sorted_items
    ]
```

- [ ] **Step 4: Run — expect 11 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_analytics_service.py -x 2>&1 | tail -10
```

Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/services/analytics.py tests/test_analytics_service.py
git commit -m "feat(phase6b): analytics service — per_post + per_tag"
```

---

## Task 10: Admin /api/admin/dashboard

**Files:**
- Create: `backend/app/routers/admin/analytics.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Create: `backend/tests/test_admin_analytics.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_admin_analytics.py`:

```python
import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import HitDaily, HitEvent

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def clean_analytics():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(HitEvent))
        await s.execute(delete(HitDaily))
        await s.commit()


async def test_dashboard_unauthenticated_401(client, clean_analytics):
    r = await client.get("/api/admin/dashboard")
    assert r.status_code == 401


async def test_dashboard_empty_returns_zeros(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["hits"]["today"] == 0
    assert body["hits"]["last_7d"] == 0
    assert body["hits"]["last_30d"] == 0
    assert "likes" in body and "comments" in body and "posts" in body and "media" in body


async def test_dashboard_today_hits_visible(client, admin_token, clean_analytics):
    from datetime import UTC, datetime
    async with AsyncSessionLocal() as s:
        for _ in range(7):
            s.add(HitEvent(path="/", created_at=datetime.now(UTC)))
        await s.commit()

    r = await client.get(
        "/api/admin/dashboard",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.json()["hits"]["today"] == 7
```

- [ ] **Step 2: Run — expect 404**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_analytics.py -x 2>&1 | tail -10
```

Expected: failures because route not registered.

- [ ] **Step 3: Write router skeleton + dashboard endpoint**

Create `backend/app/routers/admin/analytics.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.analytics import DashboardResponse
from app.services import analytics as analytics_svc

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> DashboardResponse:
    return await analytics_svc.dashboard_kpis(s)
```

- [ ] **Step 4: Register router**

In `backend/app/routers/admin/__init__.py`, add the import (alphabetical, after `account_router`):

```python
from app.routers.admin.analytics import router as analytics_router
```

And below the existing `router.include_router` lines, add:

```python
router.include_router(analytics_router, tags=["admin·analytics"])
```

- [ ] **Step 5: Run — expect 3 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_analytics.py -x 2>&1 | tail -10
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/admin/analytics.py app/routers/admin/__init__.py tests/test_admin_analytics.py
git commit -m "feat(phase6b): GET /api/admin/dashboard"
```

---

## Task 11: Admin /api/admin/analytics (bundle)

**Files:**
- Modify: `backend/app/routers/admin/analytics.py`
- Modify: `backend/tests/test_admin_analytics.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_admin_analytics.py`:

```python
async def test_analytics_unauthenticated_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics")
    assert r.status_code == 401


async def test_analytics_default_30_days(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "timeseries" in body
    assert len(body["timeseries"]) == 30
    assert all(p["hits"] == 0 for p in body["timeseries"])


async def test_analytics_days_clamp_lower(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics?days=0",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 422


async def test_analytics_days_clamp_upper(client, admin_token, clean_analytics):
    r = await client.get(
        "/api/admin/analytics?days=10000",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert len(r.json()["timeseries"]) == 365
```

- [ ] **Step 2: Run — expect 404 / no clamp**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_analytics.py -k analytics -x 2>&1 | tail -10
```

Expected: failures.

- [ ] **Step 3: Add bundle endpoint**

In `backend/app/routers/admin/analytics.py`, update the imports to include the schemas + Query type:

Replace the existing imports block with:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.analytics import AnalyticsBundleResponse, DashboardResponse
from app.services import analytics as analytics_svc
```

Append after `get_dashboard`:

```python
@router.get("/analytics", response_model=AnalyticsBundleResponse)
async def get_analytics(
    days: int = Query(default=30, ge=1, le=365),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> AnalyticsBundleResponse:
    return AnalyticsBundleResponse(
        timeseries=await analytics_svc.timeseries(s, days=days),
        top_paths=await analytics_svc.top_paths(s, days=days, limit=10),
        top_referrers=await analytics_svc.top_referrers(s, days=days, limit=10),
        top_countries=await analytics_svc.top_countries(s, days=days, limit=10),
    )
```

- [ ] **Step 4: Run — expect 7 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_analytics.py -x 2>&1 | tail -10
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/admin/analytics.py tests/test_admin_analytics.py
git commit -m "feat(phase6b): GET /api/admin/analytics (timeseries + top_*)"
```

---

## Task 12: Admin /analytics/posts + /analytics/tags

**Files:**
- Modify: `backend/app/routers/admin/analytics.py`
- Modify: `backend/tests/test_admin_analytics.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/tests/test_admin_analytics.py`:

```python
from datetime import date, timedelta

from app.models import Post, Tag


async def test_analytics_posts_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics/posts")
    assert r.status_code == 401


async def test_analytics_tags_401(client, clean_analytics):
    r = await client.get("/api/admin/analytics/tags")
    assert r.status_code == 401


async def test_analytics_posts_returns_titled_rows(
    client, admin_token, clean_analytics
):
    yesterday = date.today() - timedelta(days=1)
    slug = "p6b-analytics-posttest"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p6btest-admin-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p6btest-admin-tag", name="Admin Tag",
                      color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p6btest-admin-tag")
            )).first()
        s.add(Post(
            id=slug, n=1, title="Post Test", subtitle="", date="2026-04-28",
            read=1, lang="en", summary="", tldr="", body_md="", body_json={},
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.flush()
        s.add(HitDaily(date=yesterday, path=f"/post/{slug}",
                       hits=21, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()
    try:
        r = await client.get(
            "/api/admin/analytics/posts?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        match = next((p for p in body if p["post_id"] == slug), None)
        assert match is not None
        assert match["title"] == "Post Test"
        assert match["hits"] == 21
    finally:
        from sqlalchemy import delete as sa_delete
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(HitDaily).where(HitDaily.post_id == slug))
            await s.execute(sa_delete(Post).where(Post.id == slug))
            await s.execute(sa_delete(Tag).where(Tag.slug == "p6btest-admin-tag"))
            await s.commit()


async def test_analytics_posts_excludes_deleted(
    client, admin_token, clean_analytics
):
    """Deleting the post makes hit_daily.post_id become NULL via FK SET NULL,
    so the post no longer appears in /analytics/posts."""
    from sqlalchemy import delete as sa_delete
    yesterday = date.today() - timedelta(days=1)
    slug = "p6b-fk-test"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p6btest-fk-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p6btest-fk-tag", name="FK Tag",
                      color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p6btest-fk-tag")
            )).first()
        s.add(Post(
            id=slug, n=1, title="Will Delete", subtitle="", date="2026-04-28",
            read=1, lang="en", summary="", tldr="", body_md="", body_json={},
            word_count=0, status="published", featured=False, private=False,
            comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.flush()
        s.add(HitDaily(date=yesterday, path=f"/post/{slug}",
                       hits=5, post_id=slug,
                       referrers_top=[], countries_top=[]))
        await s.commit()

    async with AsyncSessionLocal() as s:
        await s.execute(sa_delete(Post).where(Post.id == slug))
        await s.commit()

    try:
        r = await client.get(
            "/api/admin/analytics/posts?days=7",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert all(p["post_id"] != slug for p in body)
    finally:
        async with AsyncSessionLocal() as s:
            await s.execute(sa_delete(HitDaily).where(HitDaily.path == f"/post/{slug}"))
            await s.execute(sa_delete(Tag).where(Tag.slug == "p6btest-fk-tag"))
            await s.commit()
```

- [ ] **Step 2: Run — expect 404**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_analytics.py -k "analytics_posts or analytics_tags" -x 2>&1 | tail -10
```

Expected: failures.

- [ ] **Step 3: Add /analytics/posts + /analytics/tags endpoints**

In `backend/app/routers/admin/analytics.py`, update imports — replace with:

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.analytics import (
    AnalyticsBundleResponse,
    DashboardResponse,
    PostHitsItem,
    TagHitsItem,
)
from app.services import analytics as analytics_svc
```

Append at the bottom:

```python
@router.get("/analytics/posts", response_model=list[PostHitsItem])
async def get_analytics_posts(
    days: int = Query(default=30, ge=1, le=365),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[PostHitsItem]:
    return await analytics_svc.per_post(s, days=days, limit=50)


@router.get("/analytics/tags", response_model=list[TagHitsItem])
async def get_analytics_tags(
    days: int = Query(default=30, ge=1, le=365),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[TagHitsItem]:
    return await analytics_svc.per_tag(s, days=days)
```

- [ ] **Step 4: Run — expect 11 PASS**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_admin_analytics.py -x 2>&1 | tail -10
```

Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add app/routers/admin/analytics.py tests/test_admin_analytics.py
git commit -m "feat(phase6b): GET /api/admin/analytics/posts + /tags"
```

---

## Task 13: Migration round-trip test

**Files:**
- Create: `backend/tests/test_alembic_0006_roundtrip.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_alembic_0006_roundtrip.py`:

```python
"""Round-trip alembic to 0005 and back to 0006 to exercise the downgrade."""
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

    # Restore head so other tests run against the latest schema.
    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
```

- [ ] **Step 2: Run**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest tests/test_alembic_0006_roundtrip.py -v 2>&1 | tail -10
```

Expected: `1 passed`.

- [ ] **Step 3: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && git add tests/test_alembic_0006_roundtrip.py
git commit -m "test(phase6b): alembic 0006 round-trip"
```

---

## Task 14: Final full-suite + ruff

**Files:**
- (None — verification only)

- [ ] **Step 1: Full test suite**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run pytest 2>&1 | tail -3
```

Expected: at least 338 passing (298 baseline + ~40 new tests). Report the actual number.

- [ ] **Step 2: ruff**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && uv run ruff check . 2>&1 | tail -3
```

Expected: 8 errors (P3/P4 baseline). If P6b introduced any new errors, the controller will fix them in a follow-up commit.

- [ ] **Step 3: Manual smoke (optional, run by controller post-merge)**

The plan ships without a manual smoke step — run `analytics_rollup` via curl-then-cron once the branch is merged and a real daily window has elapsed. The full test suite plus per-task tests cover all branches functionally.

- [ ] **Step 4: Final report**

Report test count, ruff diff, and any open concerns.

---

## Acceptance Criteria Mapping

| Spec §10.7 criterion | Task |
|---|---|
| `hit_events` + `hit_daily` tables; round-trip clean | 1, 13 |
| `POST /api/hit` returns 204 always | 5 |
| Bot UA dropped, 60s dedup honored | 4 (unit), 5 (HTTP) |
| Country populates from `CF-IPCountry`; NULL otherwise | 4, 5 |
| `post_id` validated; non-existent → NULL | 4, 5 |
| ARQ `analytics_rollup_task` rolls a UTC day; idempotent | 6 |
| Raw hit_events older than 30d truncated | 6 |
| `analytics.rollup` event_log fires | 6 |
| 4 admin endpoints all 401 without auth | 10, 11, 12 |
| Admin endpoints return correct counts | 10, 11, 12 |
| `/posts` + `/tags` join via post_id FK | 9, 12 |
| All P3/P4/P5/P6a tests still pass | 14 |
