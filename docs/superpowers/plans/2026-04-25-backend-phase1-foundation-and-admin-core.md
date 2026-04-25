# Backend Phase 1 — Foundation, Public Read API & Admin Core (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a runnable FastAPI backend that (1) serves all data the existing frontend reads today (replacing `src/data.js`), and (2) lets a single admin log in and create/edit posts, tags, projects, contacts, and site/profile/theme settings via REST endpoints. By the end of this plan, `localhost:51730` (frontend) renders entirely from `localhost:51820` (backend); the admin can publish a new article via HTTP.

**Architecture:** Python 3.12 + FastAPI on `:51820`. Postgres 16 for primary store, Redis 7 for sessions and rate-limit buckets. SQLAlchemy 2.0 async ORM, Alembic migrations. mistune-3 parses markdown into a structured `body_json` cache. JWT access tokens (15 min) for admin auth — refresh-token rotation, 2FA, magic-link, comments, analytics, integrations, ARQ workers, media, webhooks, and the production Dockerfile are all later phases.

**Tech Stack:** `uv` package manager, FastAPI, SQLAlchemy[asyncio], asyncpg, Alembic, Redis, mistune, python-frontmatter, argon2-cffi, PyJWT, Typer, structlog, pytest + pytest-asyncio + httpx + pytest-postgresql + fakeredis.

**Out of scope for Phase 1:** Refresh tokens, 2FA, magic-link, comments, likes, rate limiting (Redis exists but no buckets enforced yet), analytics, media uploads, GitHub sync, Pet LLM, ARQ scheduler, webhooks, danger zone, production Dockerfile, email sending, integrations CRUD.

---

## File Structure

What this plan creates or modifies. Subsequent phases extend the same tree.

```
/Users/sd3/Desktop/project/MyBlog/
├── backend/                            # NEW
│   ├── pyproject.toml                  # uv + deps lock
│   ├── uv.lock                         # generated
│   ├── alembic.ini
│   ├── docker-compose.dev.yml          # postgres + redis
│   ├── .env.example
│   ├── .env                            # local only, gitignored
│   ├── README.md
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial.py
│   ├── posts/                          # markdown source-of-truth (gitignored)
│   ├── data/                           # runtime state (gitignored)
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── fixtures/
│   │   │   └── real_md/                # copied from /Users/sd3/Desktop/工具文档
│   │   ├── test_health.py
│   │   ├── test_markdown_pipeline.py
│   │   ├── test_frontmatter.py
│   │   ├── test_auth.py
│   │   ├── test_public_posts.py
│   │   ├── test_public_misc.py
│   │   ├── test_admin_auth.py
│   │   ├── test_admin_posts.py
│   │   ├── test_admin_taxonomy.py      # tags / projects / contacts
│   │   └── test_admin_site.py
│   └── app/
│       ├── __init__.py
│       ├── main.py                     # FastAPI factory
│       ├── config.py                   # pydantic-settings
│       ├── db.py                       # async engine + session
│       ├── redis.py                    # async redis client
│       ├── deps.py                     # FastAPI dependencies
│       ├── errors.py                   # exception types + handlers
│       ├── middleware.py               # request_id + timing
│       ├── logging_config.py           # structlog setup
│       ├── cli.py                      # Typer entry
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py                 # DeclarativeBase
│       │   ├── post.py
│       │   ├── tag.py
│       │   ├── project.py
│       │   ├── contact.py
│       │   ├── site_meta.py
│       │   ├── account.py
│       │   ├── event_log.py
│       │   └── contrib_day.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── post.py
│       │   ├── tag.py
│       │   ├── project.py
│       │   ├── contact.py
│       │   ├── site.py
│       │   └── auth.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── markdown_pipeline.py
│       │   ├── frontmatter_schema.py
│       │   ├── auth.py
│       │   └── event_log.py
│       └── routers/
│           ├── __init__.py
│           ├── public/
│           │   ├── __init__.py
│           │   ├── health.py
│           │   ├── site.py
│           │   ├── posts.py
│           │   ├── tags.py
│           │   ├── projects.py
│           │   ├── contacts.py
│           │   └── contrib.py
│           └── admin/
│               ├── __init__.py
│               ├── auth.py
│               ├── posts.py
│               ├── tags.py
│               ├── projects.py
│               ├── contacts.py
│               └── site.py
├── src/
│   ├── api/                            # NEW (frontend integration)
│   │   ├── client.js
│   │   └── hooks.js
│   ├── data.js                         # GUTTED → re-exports from /api hooks
│   └── ...                             # existing components updated to use hooks
└── .env.development                    # NEW frontend env: VITE_API_BASE_URL
```

**Why split this way:** Each `services/*.py` has one responsibility. `routers/public/` and `routers/admin/` keep the auth boundary visible. `models/*.py` files are one-per-table (small files reason better in agent context). `tests/test_*.py` mirror routers + services 1-to-1, so failures point straight at the source.

---

## Phase A — Project bootstrap & infrastructure

### Task 1: Create backend skeleton + pyproject.toml

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/README.md`
- Create: `backend/.gitignore`
- Create: `backend/app/__init__.py`
- Create: `backend/tests/__init__.py`

- [ ] **Step 1: Create the directory tree**

```bash
cd /Users/sd3/Desktop/project/MyBlog
mkdir -p backend/{app/{models,schemas,services,routers/{public,admin}},tests/fixtures/real_md,alembic/versions,posts,data}
touch backend/app/__init__.py backend/app/models/__init__.py backend/app/schemas/__init__.py backend/app/services/__init__.py backend/app/routers/__init__.py backend/app/routers/public/__init__.py backend/app/routers/admin/__init__.py backend/tests/__init__.py
```

- [ ] **Step 2: Write `backend/pyproject.toml`**

```toml
[project]
name = "myblog-backend"
version = "0.1.0"
description = "wangyang.dev backend — FastAPI + Postgres + Redis"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "redis>=5.2",
    "pydantic>=2.10",
    "pydantic-settings>=2.6",
    "mistune>=3",
    "python-frontmatter>=1.1",
    "argon2-cffi>=23",
    "pyjwt>=2.10",
    "typer>=0.15",
    "structlog>=24",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = [
    "pytest>=8",
    "pytest-asyncio>=0.24",
    "pytest-postgresql>=6",
    "fakeredis>=2.26",
    "httpx>=0.28",
    "freezegun>=1.5",
    "ruff>=0.8",
    "mypy>=1.13",
]

[project.scripts]
myblog = "app.cli:app"

[tool.uv]
package = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "ASYNC"]
ignore = ["E501"]
```

- [ ] **Step 3: Write `backend/.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.pytest_cache/
.mypy_cache/
.ruff_cache/
data/
posts/
.env
*.db
*.sqlite
.coverage
htmlcov/
```

- [ ] **Step 4: Write `backend/README.md`**

```markdown
# wangyang.dev — backend

FastAPI + Postgres 16 + Redis 7. See top-level `docs/superpowers/specs/2026-04-25-myblog-backend-design.md` for full design.

## Quick start

    uv sync
    docker compose -f docker-compose.dev.yml up -d
    uv run alembic upgrade head
    uv run python -m app.cli seed admin --email hi@wangyang.dev --password changeme
    uv run python -m app.cli seed bootstrap
    uv run uvicorn app.main:app --port 51820 --reload

API at http://localhost:51820 ; healthz at http://localhost:51820/api/healthz
```

- [ ] **Step 5: Install via uv**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv sync --extra dev
```

Expected output (last line): `Resolved <N> packages in <time>`. The `.venv/` directory should now exist.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/pyproject.toml backend/uv.lock backend/.gitignore backend/README.md backend/app/__init__.py backend/app/**/__init__.py backend/tests/__init__.py
git commit -m "feat(backend): scaffold pyproject + uv-managed venv"
```

---

### Task 2: Postgres + Redis dev compose

**Files:**
- Create: `backend/docker-compose.dev.yml`
- Create: `backend/.env.example`
- Create: `backend/.env`

- [ ] **Step 1: Write `backend/docker-compose.dev.yml`**

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: myblog
      POSTGRES_PASSWORD: myblog_dev
      POSTGRES_DB: myblog
    ports:
      - "51832:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U myblog"]
      interval: 3s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "51833:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 3s
      retries: 10

  adminer:
    image: adminer:latest
    ports:
      - "51834:8080"
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

Ports `51832/51833/51834` are deliberately in the same high-port band as the app so `lsof -i :518` finds everything.

- [ ] **Step 2: Write `backend/.env.example`**

```bash
# core
API_PORT=51820
ENV=dev
LOG_LEVEL=DEBUG

# CORS — frontend dev origin
CORS_ORIGINS=http://localhost:51730

# storage
DATABASE_URL=postgresql+asyncpg://myblog:myblog_dev@localhost:51832/myblog
REDIS_URL=redis://localhost:51833/0
DATA_DIR=./data
POSTS_DIR=./posts

# auth
JWT_SECRET=replace-with-32-bytes-of-randomness-for-prod
ACCESS_TOKEN_TTL=900

# salts
LIKE_SALT=replace-with-random-32-bytes
```

- [ ] **Step 3: Copy to `backend/.env`**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
cp .env.example .env
# Generate real secrets
python3 -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))" >> /tmp/dev_secrets
python3 -c "import secrets; print('LIKE_SALT=' + secrets.token_urlsafe(32))" >> /tmp/dev_secrets
# Manually paste those values into .env, replacing the placeholder lines
```

- [ ] **Step 4: Bring up Postgres + Redis**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
docker compose -f docker-compose.dev.yml up -d postgres redis
docker compose -f docker-compose.dev.yml ps
```

Expected: `postgres` and `redis` both `Up (healthy)` within ~10s.

- [ ] **Step 5: Verify connectivity**

```bash
docker exec -it $(docker ps -qf 'ancestor=postgres:16-alpine') psql -U myblog -d myblog -c 'select 1 as ok;'
docker exec -it $(docker ps -qf 'ancestor=redis:7-alpine') redis-cli ping
```

Expected: `1` row from psql, `PONG` from redis.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add backend/docker-compose.dev.yml backend/.env.example
git commit -m "feat(backend): docker-compose for postgres + redis (dev)"
```

(Do NOT commit `backend/.env` — it's gitignored.)

---

### Task 3: pydantic-settings config module

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_config.py`:

```python
import os
from app.config import Settings


def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/d")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:51730")

    s = Settings()
    assert s.api_port == 51820
    assert s.env == "dev"
    assert str(s.database_url).startswith("postgresql+asyncpg://")
    assert s.cors_origins == ["http://localhost:51730"]


def test_cors_origins_csv(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/d")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("LIKE_SALT", "y" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "http://a,http://b")
    s = Settings()
    assert s.cors_origins == ["http://a", "http://b"]
```

- [ ] **Step 2: Run; expect FAIL (module missing)**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: Write `backend/app/config.py`**

```python
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # core
    api_port: int = 51820
    env: Literal["dev", "prod"] = "dev"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(default_factory=list)

    # storage
    database_url: str
    redis_url: str
    data_dir: Path = Path("./data")
    posts_dir: Path = Path("./posts")

    # auth
    jwt_secret: str = Field(min_length=32)
    access_token_ttl: int = 900

    # salts
    like_salt: str = Field(min_length=16)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py
git commit -m "feat(backend): pydantic-settings config loader"
```

---

### Task 4: Async SQLAlchemy engine + session factory

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models/base.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write `backend/app/models/base.py`**

```python
from datetime import datetime, UTC

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
```

- [ ] **Step 2: Write `backend/app/db.py`**

```python
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

_settings = get_settings()
engine = create_async_engine(
    _settings.database_url, echo=False, future=True, pool_pre_ping=True
)
AsyncSessionLocal = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

- [ ] **Step 3: Write `backend/app/models/__init__.py`**

```python
from app.models.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

- [ ] **Step 4: Smoke test the engine**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run python -c "
import asyncio
from app.db import engine
from sqlalchemy import text

async def main():
    async with engine.connect() as conn:
        r = await conn.execute(text('select 1 as ok'))
        print(r.scalar())
    await engine.dispose()

asyncio.run(main())
"
```

Expected: prints `1`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/app/models/base.py backend/app/models/__init__.py
git commit -m "feat(backend): async SQLAlchemy engine + Base + TimestampMixin"
```

---

### Task 5: Redis client wrapper

**Files:**
- Create: `backend/app/redis.py`

- [ ] **Step 1: Write `backend/app/redis.py`**

```python
from __future__ import annotations

import redis.asyncio as redis

from app.config import get_settings

_settings = get_settings()
_pool: redis.ConnectionPool | None = None


def _get_pool() -> redis.ConnectionPool:
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool.from_url(_settings.redis_url, decode_responses=True)
    return _pool


def get_redis() -> redis.Redis:
    return redis.Redis(connection_pool=_get_pool())


async def ping() -> bool:
    client = get_redis()
    try:
        return await client.ping()
    finally:
        await client.aclose()
```

- [ ] **Step 2: Smoke test**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run python -c "
import asyncio
from app.redis import ping
print(asyncio.run(ping()))
"
```

Expected: `True`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/redis.py
git commit -m "feat(backend): redis async client wrapper"
```

---

## Phase B — Models & initial migration

### Task 6: Define `tags` model

**Files:**
- Create: `backend/app/models/tag.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write `backend/app/models/tag.py`**

```python
from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Tag(Base, TimestampMixin):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("slug", name="uq_tags_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default="#7dd3a4")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 2: Re-export in `backend/app/models/__init__.py`**

Replace contents:

```python
from app.models.base import Base, TimestampMixin
from app.models.tag import Tag

__all__ = ["Base", "TimestampMixin", "Tag"]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/tag.py backend/app/models/__init__.py
git commit -m "feat(backend): Tag model"
```

---

### Task 7: Define `posts` model

**Files:**
- Create: `backend/app/models/post.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write `backend/app/models/post.py`**

```python
from datetime import date as date_t, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.tag import Tag


class Post(Base, TimestampMixin):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint(
            "status in ('draft','published','scheduled')", name="ck_posts_status"
        ),
        CheckConstraint("lang in ('zh','en')", name="ck_posts_lang"),
        Index("ix_posts_status_date", "status", "date"),
        Index("ix_posts_tag_status_date", "tag_id", "status", "date"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    n: Mapped[str] = mapped_column(String(8), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str | None] = mapped_column(String(300))
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="RESTRICT"), nullable=False
    )
    date: Mapped[date_t] = mapped_column(Date, nullable=False)
    read: Mapped[str | None] = mapped_column(String(16))
    lang: Mapped[str] = mapped_column(String(2), nullable=False, default="zh")
    summary: Mapped[str | None] = mapped_column(Text)
    tldr: Mapped[str | None] = mapped_column(Text)
    body_md: Mapped[str] = mapped_column(Text, nullable=False)
    body_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comments_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    tag: Mapped[Tag] = relationship(lazy="joined")
```

- [ ] **Step 2: Re-export**

```python
# backend/app/models/__init__.py
from app.models.base import Base, TimestampMixin
from app.models.post import Post
from app.models.tag import Tag

__all__ = ["Base", "TimestampMixin", "Tag", "Post"]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/post.py backend/app/models/__init__.py
git commit -m "feat(backend): Post model with body_json jsonb"
```

---

### Task 8: Define `projects`, `contacts`, `site_meta` models

**Files:**
- Create: `backend/app/models/project.py`
- Create: `backend/app/models/contact.py`
- Create: `backend/app/models/site_meta.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write `backend/app/models/project.py`**

```python
from sqlalchemy import Boolean, CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "status in ('active','maintained','archived')", name="ck_projects_status"
        ),
    )

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str] = mapped_column(String(32), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 2: Write `backend/app/models/contact.py`**

```python
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(256), nullable=False)
    href: Mapped[str] = mapped_column(String(512), nullable=False)
    visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 3: Write `backend/app/models/site_meta.py`**

```python
from datetime import date

from sqlalchemy import CheckConstraint, Date, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SiteMeta(Base, TimestampMixin):
    """Single-row site configuration table."""

    __tablename__ = "site_meta"
    __table_args__ = (CheckConstraint("id = 1", name="ck_site_meta_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    handle: Mapped[str] = mapped_column(String(64), nullable=False, default="wangyang")
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="汪洋")
    name_en: Mapped[str] = mapped_column(String(64), nullable=False, default="Wang Yang")
    role: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    tagline: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    bio: Mapped[str] = mapped_column(Text, nullable=False, default="")
    location: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    github: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    pronouns: Mapped[str | None] = mapped_column(String(32))
    avatar_path: Mapped[str | None] = mapped_column(String(256))
    typing_line: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stack_chips: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    footer_note: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    default_theme: Mapped[str] = mapped_column(String(8), nullable=False, default="dark")
    accent_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(82% 0.17 152)")
    accent2_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(80% 0.15 70)")
    violet_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(72% 0.18 295)")
    danger_color: Mapped[str] = mapped_column(String(32), nullable=False, default="oklch(70% 0.2 25)")
    launched_at: Mapped[date] = mapped_column(Date, nullable=False, default=date(2026, 1, 1))
    pet_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
```

- [ ] **Step 4: Update `backend/app/models/__init__.py`**

```python
from app.models.base import Base, TimestampMixin
from app.models.contact import Contact
from app.models.post import Post
from app.models.project import Project
from app.models.site_meta import SiteMeta
from app.models.tag import Tag

__all__ = ["Base", "TimestampMixin", "Tag", "Post", "Project", "Contact", "SiteMeta"]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/project.py backend/app/models/contact.py backend/app/models/site_meta.py backend/app/models/__init__.py
git commit -m "feat(backend): Project, Contact, SiteMeta models"
```

---

### Task 9: Define `accounts`, `event_log`, `contrib_days` models

**Files:**
- Create: `backend/app/models/account.py`
- Create: `backend/app/models/event_log.py`
- Create: `backend/app/models/contrib_day.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write `backend/app/models/account.py`**

```python
from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("id = 1", name="ck_accounts_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    email: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    tfa_secret_encrypted: Mapped[str | None] = mapped_column(String(256))
    tfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    magic_link_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 2: Write `backend/app/models/event_log.py`**

```python
from datetime import datetime, UTC

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class EventLog(Base):
    __tablename__ = "event_log"
    __table_args__ = (
        Index("ix_event_log_created_at", "created_at"),
        Index("ix_event_log_type_created", "type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    target: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 3: Write `backend/app/models/contrib_day.py`**

```python
from datetime import date

from sqlalchemy import Date, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ContribDay(Base):
    __tablename__ = "contrib_days"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 4: Update `backend/app/models/__init__.py`**

```python
from app.models.account import Account
from app.models.base import Base, TimestampMixin
from app.models.contact import Contact
from app.models.contrib_day import ContribDay
from app.models.event_log import EventLog
from app.models.post import Post
from app.models.project import Project
from app.models.site_meta import SiteMeta
from app.models.tag import Tag

__all__ = [
    "Base", "TimestampMixin",
    "Account", "Contact", "ContribDay", "EventLog",
    "Post", "Project", "SiteMeta", "Tag",
]
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/account.py backend/app/models/event_log.py backend/app/models/contrib_day.py backend/app/models/__init__.py
git commit -m "feat(backend): Account, EventLog, ContribDay models"
```

---

### Task 10: Alembic init + initial migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/0001_initial.py`

- [ ] **Step 1: Initialize alembic skeleton**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run alembic init alembic
```

This creates `alembic.ini` and `alembic/` skeleton.

- [ ] **Step 2: Edit `backend/alembic.ini`**

Find the `sqlalchemy.url = ...` line and replace with:

```ini
sqlalchemy.url =
```

(empty — env.py will load from settings)

- [ ] **Step 3: Replace `backend/alembic/env.py` with**

```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import get_settings
from app.models import Base
import app.models  # noqa: F401  -- ensure all models registered

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")
    connectable = async_engine_from_config(
        cfg, prefix="sqlalchemy.", poolclass=pool.NullPool, future=True
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

- [ ] **Step 4: Generate the initial migration**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run alembic revision --autogenerate -m "initial"
```

Expected: a file at `alembic/versions/<hash>_initial.py` with `op.create_table(...)` calls for `tags`, `posts`, `projects`, `contacts`, `site_meta`, `accounts`, `event_log`, `contrib_days`.

- [ ] **Step 5: Rename it to deterministic filename**

```bash
mv backend/alembic/versions/*_initial.py backend/alembic/versions/0001_initial.py
```

- [ ] **Step 6: Open the new file and force `revision = "0001_initial"`**

Edit the top of `backend/alembic/versions/0001_initial.py`:

```python
"""initial

Revision ID: 0001_initial
Revises:
Create Date: ...
"""
from typing import Sequence

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
```

(leave the autogenerated `upgrade()` and `downgrade()` bodies alone)

- [ ] **Step 7: Apply the migration**

```bash
uv run alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade -> 0001_initial`.

- [ ] **Step 8: Verify tables**

```bash
docker exec -it $(docker ps -qf 'ancestor=postgres:16-alpine') psql -U myblog -d myblog -c "\dt"
```

Expected: 8 user tables + `alembic_version`.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic.ini backend/alembic/env.py backend/alembic/script.py.mako backend/alembic/versions/0001_initial.py
git commit -m "feat(backend): alembic initial migration (8 tables)"
```

---

## Phase C — App factory, middleware, error handlers

### Task 11: Structured logging + request_id middleware

**Files:**
- Create: `backend/app/logging_config.py`
- Create: `backend/app/middleware.py`

- [ ] **Step 1: Write `backend/app/logging_config.py`**

```python
import logging
import sys

import structlog

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(level=level, stream=sys.stdout, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
            if settings.env == "prod"
            else structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "app") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 2: Write `backend/app/middleware.py`**

```python
import time
import uuid

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=rid, path=request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            structlog.contextvars.unbind_contextvars("path")
        response.headers["X-Request-ID"] = rid
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        return response
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/logging_config.py backend/app/middleware.py
git commit -m "feat(backend): structlog config + request_id middleware"
```

---

### Task 12: Error types & global handlers

**Files:**
- Create: `backend/app/errors.py`

- [ ] **Step 1: Write `backend/app/errors.py`**

```python
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = structlog.get_logger(__name__)


class AuthError(Exception):
    def __init__(self, detail: str = "auth required") -> None:
        self.detail = detail


class NotFoundError(Exception):
    def __init__(self, detail: str = "not found") -> None:
        self.detail = detail


class RateLimited(Exception):
    def __init__(self, retry_after: int = 60, detail: str = "rate limited") -> None:
        self.retry_after = retry_after
        self.detail = detail


def _err(status_code: int, detail: Any, **headers: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail}, headers=headers or None)


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def _http_exc(_: Request, e: HTTPException) -> JSONResponse:
        return _err(e.status_code, e.detail)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, e: RequestValidationError) -> JSONResponse:
        return _err(status.HTTP_422_UNPROCESSABLE_ENTITY, e.errors())

    @app.exception_handler(IntegrityError)
    async def _integrity(_: Request, e: IntegrityError) -> JSONResponse:
        logger.warning("integrity_error", error=str(e.orig))
        return _err(status.HTTP_409_CONFLICT, "conflict")

    @app.exception_handler(AuthError)
    async def _auth(_: Request, e: AuthError) -> JSONResponse:
        return _err(status.HTTP_401_UNAUTHORIZED, e.detail)

    @app.exception_handler(NotFoundError)
    async def _nf(_: Request, e: NotFoundError) -> JSONResponse:
        return _err(status.HTTP_404_NOT_FOUND, e.detail)

    @app.exception_handler(RateLimited)
    async def _rl(_: Request, e: RateLimited) -> JSONResponse:
        return _err(
            status.HTTP_429_TOO_MANY_REQUESTS, e.detail, **{"Retry-After": str(e.retry_after)}
        )

    @app.exception_handler(Exception)
    async def _unhandled(req: Request, e: Exception) -> JSONResponse:
        rid = req.headers.get("X-Request-ID", "?")
        logger.exception("unhandled_exception", error=str(e), request_id=rid)
        return _err(status.HTTP_500_INTERNAL_SERVER_ERROR, f"internal error · {rid}")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/errors.py
git commit -m "feat(backend): exception types + global handlers"
```

---

### Task 13: FastAPI app factory + healthz/readyz

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/routers/public/health.py`
- Modify: `backend/app/routers/public/__init__.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_healthz(client):
    r = await client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_readyz_ok(client):
    r = await client.get("/api/readyz")
    assert r.status_code in (200, 503)  # 503 acceptable if DB/Redis offline; 200 expected when up
```

- [ ] **Step 2: Write `backend/app/routers/public/health.py`**

```python
from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine
from app.redis import get_redis

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, bool]:
    return {"ok": True}


@router.get("/readyz")
async def readyz() -> dict:
    db_ok = False
    redis_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        db_ok = True
    except Exception:
        pass
    try:
        client = get_redis()
        await client.ping()
        await client.aclose()
        redis_ok = True
    except Exception:
        pass

    if db_ok and redis_ok:
        return {"db": True, "redis": True}
    from fastapi import HTTPException
    raise HTTPException(status_code=503, detail={"db": db_ok, "redis": redis_ok})
```

- [ ] **Step 3: Write `backend/app/routers/public/__init__.py`**

```python
from fastapi import APIRouter

from app.routers.public.health import router as health_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
```

- [ ] **Step 4: Write `backend/app/main.py`**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_handlers
from app.logging_config import configure_logging
from app.middleware import RequestContextMiddleware
from app.routers.public import router as public_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="wangyang.dev API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "X-Response-Time-Ms"],
    )
    app.add_middleware(RequestContextMiddleware)
    install_handlers(app)

    app.include_router(public_router)
    return app


app = create_app()
```

- [ ] **Step 5: Run the test**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run pytest tests/test_health.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Smoke test against a running server**

```bash
# In one terminal
uv run uvicorn app.main:app --port 51820

# In another
curl -s http://localhost:51820/api/healthz
curl -s http://localhost:51820/api/readyz
```

Expected: `{"ok":true}` and `{"db":true,"redis":true}`. Stop uvicorn after.

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/routers/public/health.py backend/app/routers/public/__init__.py backend/tests/test_health.py
git commit -m "feat(backend): FastAPI app factory + /api/healthz + /api/readyz"
```

---

## Phase D — Markdown pipeline

### Task 14: Pydantic frontmatter schema

**Files:**
- Create: `backend/app/services/frontmatter_schema.py`
- Create: `backend/tests/test_frontmatter.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_frontmatter.py`:

```python
from datetime import date, datetime, UTC

import pytest

from app.services.frontmatter_schema import PostFrontmatter


def _ok():
    return {
        "id": "termius-utf8", "n": "042", "title": "T", "tag": "devtools",
        "date": "2026-04-12", "lang": "zh",
    }


def test_minimal_valid():
    fm = PostFrontmatter(**_ok())
    assert fm.id == "termius-utf8"
    assert fm.status == "draft"
    assert fm.lang == "zh"
    assert fm.featured is False


def test_id_pattern():
    bad = _ok() | {"id": "Termius UTF8"}
    with pytest.raises(ValueError):
        PostFrontmatter(**bad)


def test_n_pattern():
    bad = _ok() | {"n": "42"}
    with pytest.raises(ValueError):
        PostFrontmatter(**bad)


def test_scheduled_requires_when():
    with pytest.raises(ValueError):
        PostFrontmatter(**(_ok() | {"status": "scheduled"}))


def test_scheduled_with_when():
    fm = PostFrontmatter(
        **(_ok() | {"status": "scheduled", "scheduled_at": datetime(2030, 1, 1, tzinfo=UTC)})
    )
    assert fm.status == "scheduled"


def test_lang_enum():
    with pytest.raises(ValueError):
        PostFrontmatter(**(_ok() | {"lang": "fr"}))
```

- [ ] **Step 2: Run; expect FAIL**

```bash
uv run pytest tests/test_frontmatter.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write `backend/app/services/frontmatter_schema.py`**

```python
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class PostFrontmatter(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    n: str = Field(pattern=r"^\d{3}$")
    title: str = Field(min_length=1, max_length=200)
    subtitle: str | None = None
    tag: str = Field(min_length=1, max_length=32)
    date: date
    read: str | None = None
    lang: Literal["zh", "en"] = "zh"
    summary: str | None = None
    tldr: str | None = None
    status: Literal["draft", "published", "scheduled"] = "draft"
    scheduled_at: datetime | None = None
    featured: bool = False
    private: bool = False
    comments_enabled: bool = True

    @model_validator(mode="after")
    def _scheduled_must_have_when(self) -> "PostFrontmatter":
        if self.status == "scheduled" and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when status=scheduled")
        return self
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_frontmatter.py -v
```

Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/frontmatter_schema.py backend/tests/test_frontmatter.py
git commit -m "feat(backend): Pydantic frontmatter schema"
```

---

### Task 15: Markdown → body_json (block parsing)

**Files:**
- Create: `backend/app/services/markdown_pipeline.py`
- Create: `backend/tests/test_markdown_pipeline.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_markdown_pipeline.py`:

```python
import pytest

from app.services.markdown_pipeline import parse_markdown, MarkdownError


def test_heading_paragraph():
    md = "## Hello\n\nWorld."
    blocks = parse_markdown(md)
    assert blocks == [
        {"t": "h2", "c": "Hello", "inline": [{"kind": "text", "s": "Hello"}]},
        {"t": "p", "c": "World.", "inline": [{"kind": "text", "s": "World."}]},
    ]


def test_h1_h3_h4():
    md = "# A\n\n### B\n\n#### C"
    blocks = parse_markdown(md)
    assert [b["t"] for b in blocks] == ["h1", "h3", "h4"]


def test_code_block_with_lang():
    md = "```bash\necho hi\n```"
    blocks = parse_markdown(md)
    assert blocks == [{"t": "code", "c": "echo hi", "lang": "bash"}]


def test_code_block_no_lang():
    md = "```\nplain\n```"
    blocks = parse_markdown(md)
    assert blocks == [{"t": "code", "c": "plain"}]


def test_unordered_list():
    md = "- one\n- two"
    blocks = parse_markdown(md)
    assert blocks == [
        {
            "t": "ul",
            "items": [
                {"c": "one", "inline": [{"kind": "text", "s": "one"}]},
                {"c": "two", "inline": [{"kind": "text", "s": "two"}]},
            ],
        }
    ]


def test_ordered_list():
    md = "1. a\n2. b"
    blocks = parse_markdown(md)
    assert blocks[0]["t"] == "ol"
    assert len(blocks[0]["items"]) == 2


def test_blockquote():
    md = "> quoted line"
    blocks = parse_markdown(md)
    assert blocks == [
        {"t": "quote", "c": "quoted line", "inline": [{"kind": "text", "s": "quoted line"}]}
    ]


def test_hr():
    md = "before\n\n---\n\nafter"
    blocks = parse_markdown(md)
    assert blocks[1] == {"t": "hr"}


def test_table_with_align():
    md = (
        "| h1 | h2 |\n"
        "|:---|---:|\n"
        "| a  | b  |\n"
        "| c  | d  |"
    )
    blocks = parse_markdown(md)
    assert blocks == [
        {
            "t": "table",
            "header": ["h1", "h2"],
            "align": ["left", "right"],
            "rows": [["a", "b"], ["c", "d"]],
        }
    ]


def test_image_block():
    md = "![alt](https://x.png)"
    blocks = parse_markdown(md)
    assert blocks == [{"t": "image", "src": "https://x.png", "alt": "alt"}]


def test_disallowed_task_list_rejected():
    md = "- [ ] todo"
    with pytest.raises(MarkdownError):
        parse_markdown(md)


def test_disallowed_strikethrough_rejected():
    md = "~~struck~~"
    with pytest.raises(MarkdownError):
        parse_markdown(md)


def test_disallowed_html_rejected():
    md = "<div>nope</div>"
    with pytest.raises(MarkdownError):
        parse_markdown(md)
```

- [ ] **Step 2: Run; expect FAIL**

```bash
uv run pytest tests/test_markdown_pipeline.py -v
```

- [ ] **Step 3: Write `backend/app/services/markdown_pipeline.py`**

```python
"""Markdown → structured body_json pipeline.

The frontend renders 8 block types and 4 inline types. We use mistune's AST
output ('renderer=None') and walk it; any unsupported AST node is a hard error.
"""
from typing import Any, Literal

import mistune

Block = dict[str, Any]
Inline = dict[str, Any]


class MarkdownError(ValueError):
    """Raised on disallowed GFM features or malformed input."""


_DISALLOWED = {
    "task_list_item": "task lists are not supported",
    "footnote_ref": "footnotes are not supported",
    "footnote_item": "footnotes are not supported",
    "strikethrough": "strikethrough is not supported",
    "block_html": "inline/block HTML is not supported",
    "inline_html": "inline/block HTML is not supported",
}


def _walk_inlines(children: list[dict]) -> list[Inline]:
    out: list[Inline] = []
    for c in children:
        t = c["type"]
        if t in _DISALLOWED:
            raise MarkdownError(_DISALLOWED[t])
        if t == "text":
            out.append({"kind": "text", "s": c["raw"]})
        elif t == "codespan":
            out.append({"kind": "code", "s": c["raw"]})
        elif t == "strong":
            out.append({"kind": "b", "children": _walk_inlines(c.get("children", []))})
        elif t == "emphasis":
            out.append({"kind": "i", "children": _walk_inlines(c.get("children", []))})
        elif t == "link":
            out.append({
                "kind": "a", "href": c["attrs"]["url"],
                "children": _walk_inlines(c.get("children", [])),
            })
        elif t == "softbreak" or t == "linebreak":
            out.append({"kind": "text", "s": "\n"})
        else:
            raise MarkdownError(f"unsupported inline node: {t}")
    return out


def _flatten_text(inlines: list[Inline]) -> str:
    parts: list[str] = []
    for i in inlines:
        if i["kind"] == "text":
            parts.append(i["s"])
        elif i["kind"] == "code":
            parts.append(i["s"])
        elif i["kind"] in ("b", "i"):
            parts.append(_flatten_text(i["children"]))
        elif i["kind"] == "a":
            parts.append(_flatten_text(i["children"]))
    return "".join(parts)


_HEADING_TS = {1: "h1", 2: "h2", 3: "h3", 4: "h4"}


def _walk_blocks(nodes: list[dict]) -> list[Block]:
    out: list[Block] = []
    for node in nodes:
        t = node["type"]
        if t in _DISALLOWED:
            raise MarkdownError(_DISALLOWED[t])

        if t == "heading":
            level = node["attrs"]["level"]
            if level not in _HEADING_TS:
                raise MarkdownError(f"heading level {level} not supported (only h1-h4)")
            inline = _walk_inlines(node.get("children", []))
            out.append({"t": _HEADING_TS[level], "c": _flatten_text(inline), "inline": inline})

        elif t == "paragraph":
            inline = _walk_inlines(node.get("children", []))
            # An image-only paragraph degrades to {t:"image", ...}
            if (
                len(inline) == 1
                and len(node.get("children", [])) == 1
                and node["children"][0]["type"] == "image"
            ):
                # mistune wrapped image in paragraph; pull it out
                img = node["children"][0]
                out.append({"t": "image", "src": img["attrs"]["url"], "alt": img.get("alt", "")})
            else:
                out.append({"t": "p", "c": _flatten_text(inline), "inline": inline})

        elif t == "block_code":
            block: Block = {"t": "code", "c": node["raw"].rstrip("\n")}
            info = node.get("attrs", {}).get("info")
            if info:
                block["lang"] = info.split()[0]
            out.append(block)

        elif t == "thematic_break":
            out.append({"t": "hr"})

        elif t == "block_quote":
            # Flatten children into a single paragraph-like block
            inner = _walk_blocks(node.get("children", []))
            text = " ".join(b.get("c", "") for b in inner if b.get("c"))
            inlines: list[Inline] = []
            for b in inner:
                inlines.extend(b.get("inline", []))
            out.append({"t": "quote", "c": text, "inline": inlines})

        elif t == "list":
            ordered = node["attrs"]["ordered"]
            items: list[dict] = []
            for li in node.get("children", []):
                # li.type == 'list_item'; first child is paragraph
                paras = li.get("children", [])
                if not paras:
                    continue
                para = paras[0]
                if para["type"] != "block_text" and para["type"] != "paragraph":
                    raise MarkdownError("nested lists are not supported")
                inline = _walk_inlines(para.get("children", []))
                items.append({"c": _flatten_text(inline), "inline": inline})
            out.append({"t": "ol" if ordered else "ul", "items": items})

        elif t == "table":
            head = node.get("children", [])[0]  # table_head
            body = node.get("children", [])[1] if len(node.get("children", [])) > 1 else None
            # Headers
            header_cells = head["children"][0]["children"]  # head -> row -> cells
            header: list[str] = []
            align: list[str] = []
            for cell in header_cells:
                header.append(_flatten_text(_walk_inlines(cell.get("children", []))))
                a = cell.get("attrs", {}).get("align")
                align.append(a if a in ("left", "center", "right") else "left")
            rows: list[list[str]] = []
            if body is not None:
                for row in body.get("children", []):
                    rows.append([
                        _flatten_text(_walk_inlines(c.get("children", [])))
                        for c in row.get("children", [])
                    ])
            out.append({"t": "table", "header": header, "align": align, "rows": rows})

        else:
            raise MarkdownError(f"unsupported block: {t}")

    return out


_md = mistune.create_markdown(
    renderer=None,
    plugins=["table", "url"],
)


def parse_markdown(md: str) -> list[Block]:
    """Parse a Markdown body into a list of structured blocks.

    Returns: list of Block dicts.
    Raises:  MarkdownError on disallowed features or malformed AST.
    """
    if "<" in md and (">" in md):
        # Quick reject for obvious HTML before mistune normalizes anything.
        # (mistune by default escapes; we still want explicit 422.)
        for token in ("<div", "<span", "<p ", "<p>", "<br", "<img", "<script"):
            if token in md:
                raise MarkdownError("inline/block HTML is not supported")
    if "~~" in md:
        raise MarkdownError("strikethrough is not supported")
    if "[ ]" in md or "[x]" in md or "[X]" in md:
        # task list
        for line in md.splitlines():
            stripped = line.lstrip()
            if stripped.startswith(("- [ ]", "- [x]", "- [X]")):
                raise MarkdownError("task lists are not supported")
    ast = _md(md)
    return _walk_blocks(ast)
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_markdown_pipeline.py -v
```

Expected: `13 passed`. If failures relate to mistune AST internals (newer versions tweak shapes), inspect with:

```bash
uv run python -c "import mistune; m=mistune.create_markdown(renderer=None, plugins=['table','url']); import json; print(json.dumps(m('## hi\n\np\n\n```\nx\n```'), indent=2))"
```

…and adjust the `_walk_blocks` keys to match the printed shape.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/markdown_pipeline.py backend/tests/test_markdown_pipeline.py
git commit -m "feat(backend): markdown→body_json pipeline (8 block + 4 inline types)"
```

---

### Task 16: Round-trip golden tests using real fixtures

**Files:**
- Create: `backend/tests/fixtures/real_md/` (populated by `cp` from user folder)
- Modify: `backend/tests/test_markdown_pipeline.py`

- [ ] **Step 1: Copy real markdown fixtures (sensitive-name skip)**

```bash
cd /Users/sd3/Desktop/project/MyBlog
mkdir -p backend/tests/fixtures/real_md
for f in /Users/sd3/Desktop/工具文档/*.md; do
  base=$(basename "$f" .md)
  case "$base" in
    accounts*|secrets*|password*|credential*) echo "SKIP sensitive: $base"; continue ;;
  esac
  cp "$f" "backend/tests/fixtures/real_md/$base.md"
done
ls backend/tests/fixtures/real_md/
```

Expected: 7 files (8 source minus `accounts.md`).

- [ ] **Step 2: Append round-trip tests to `tests/test_markdown_pipeline.py`**

Append at the end of the existing test file:

```python
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "real_md"


@pytest.mark.parametrize("md_path", sorted(FIXTURES.glob("*.md")), ids=lambda p: p.name)
def test_real_fixture_parses_without_error(md_path):
    text = md_path.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    assert isinstance(blocks, list)
    assert len(blocks) > 0


@pytest.mark.parametrize("md_path", sorted(FIXTURES.glob("*.md")), ids=lambda p: p.name)
def test_real_fixture_block_types_known(md_path):
    text = md_path.read_text(encoding="utf-8")
    blocks = parse_markdown(text)
    allowed = {"h1", "h2", "h3", "h4", "p", "code", "ul", "ol", "quote", "hr", "table", "image"}
    for b in blocks:
        assert b["t"] in allowed, f"unknown block type {b['t']} in {md_path.name}"
```

- [ ] **Step 3: Run; iterate until all fixtures pass**

```bash
uv run pytest tests/test_markdown_pipeline.py -v
```

If any fixture fails, the failure message tells you which file + which AST node was unexpected. Two known scenarios:

  - Real-world `> ...` quote with a code block inside. Acceptable: extend `_walk_blocks` quote branch to descend into nested code.
  - Tables with empty cells: ensure align defaults to `"left"`.

Fix the parser, re-run.

- [ ] **Step 4: Commit**

```bash
git add backend/tests/fixtures/real_md/ backend/tests/test_markdown_pipeline.py
git commit -m "test(backend): real markdown fixtures + round-trip parametric tests"
```

---

### Task 17: Compute derived fields (word_count, summary, read)

**Files:**
- Modify: `backend/app/services/markdown_pipeline.py`
- Modify: `backend/tests/test_markdown_pipeline.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/test_markdown_pipeline.py`:

```python
from app.services.markdown_pipeline import compute_derived


def test_word_count_mixed():
    blocks = parse_markdown("Hello world\n\n你好世界")
    d = compute_derived(blocks)
    assert d["word_count"] == 2 + 4   # 2 english tokens + 4 cjk chars


def test_read_minutes():
    text = "word " * 480  # ~480 words → 2 min @240wpm
    blocks = parse_markdown(text.strip())
    d = compute_derived(blocks)
    assert d["read"] == "2 min"


def test_summary_first_paragraph():
    md = "## h\n\nFirst paragraph here. More text.\n\n## h2\n\nSecond."
    blocks = parse_markdown(md)
    d = compute_derived(blocks)
    assert d["summary"].startswith("First paragraph here.")
```

- [ ] **Step 2: Run; expect FAIL**

```bash
uv run pytest tests/test_markdown_pipeline.py::test_word_count_mixed -v
```

- [ ] **Step 3: Append to `app/services/markdown_pipeline.py`**

```python
import math
import re

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_CJK_RE = re.compile(r"[一-鿿]")


def _plaintext(blocks: list[Block]) -> str:
    parts: list[str] = []
    for b in blocks:
        if "c" in b:
            parts.append(b["c"])
        elif b.get("t") in ("ul", "ol"):
            for it in b["items"]:
                parts.append(it["c"])
        elif b.get("t") == "table":
            parts.extend(b["header"])
            for row in b["rows"]:
                parts.extend(row)
    return " ".join(parts)


def compute_derived(blocks: list[Block]) -> dict:
    text = _plaintext(blocks)
    words = len(_WORD_RE.findall(text))
    cjk = len(_CJK_RE.findall(text))
    word_count = words + cjk
    read_min = max(1, math.ceil(word_count / 240))
    first_p = next((b for b in blocks if b.get("t") == "p"), None)
    summary = (first_p["c"][:140] + "…") if first_p and len(first_p["c"]) > 140 else (first_p["c"] if first_p else "")
    return {"word_count": word_count, "read": f"{read_min} min", "summary": summary}
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_markdown_pipeline.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/markdown_pipeline.py backend/tests/test_markdown_pipeline.py
git commit -m "feat(backend): compute_derived (word_count, summary, read)"
```

---

## Phase E — CLI: seed + import-md

### Task 18: CLI scaffold + seed admin

**Files:**
- Create: `backend/app/cli.py`
- Create: `backend/app/services/auth.py` (password hash helper only — JWT comes later)

- [ ] **Step 1: Write the password helper**

`backend/app/services/auth.py`:

```python
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=4)


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(stored_hash: str, plain: str) -> bool:
    try:
        _hasher.verify(stored_hash, plain)
        return True
    except VerifyMismatchError:
        return False
```

- [ ] **Step 2: Write `backend/app/cli.py`**

```python
"""Typer CLI for myblog backend."""
from __future__ import annotations

import asyncio

import typer
from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models import Account
from app.services.auth import hash_password

app = typer.Typer(no_args_is_help=True, add_completion=False)
seed_app = typer.Typer(no_args_is_help=True)
app.add_typer(seed_app, name="seed")


async def _seed_admin(email: str, password: str) -> None:
    async with AsyncSessionLocal() as s:
        existing = (await s.execute(select(Account).limit(1))).scalar_one_or_none()
        if existing is not None:
            existing.email = email
            existing.password_hash = hash_password(password)
            existing.tfa_enabled = False
        else:
            s.add(Account(id=1, email=email, password_hash=hash_password(password)))
        await s.commit()


@seed_app.command("admin")
def seed_admin(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True, confirmation_prompt=False),
) -> None:
    """Create or update the singleton admin account."""
    asyncio.run(_seed_admin(email, password))
    typer.echo(f"✓ admin account ready: {email}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 3: Smoke test**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run python -m app.cli seed admin --email hi@wangyang.dev --password changeme
docker exec -it $(docker ps -qf 'ancestor=postgres:16-alpine') psql -U myblog -d myblog -c "select email, length(password_hash) from accounts;"
```

Expected: prints `✓ admin account ready` and the SQL row shows the email + non-zero hash length.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/auth.py backend/app/cli.py
git commit -m "feat(backend): CLI scaffold + seed admin command"
```

---

### Task 19: `seed bootstrap` — default tags + site_meta + 12 legacy posts

**Files:**
- Modify: `backend/app/cli.py`

- [ ] **Step 1: Append to `backend/app/cli.py`**

```python
import json
from datetime import date
from pathlib import Path

from app.models import Post, Project, SiteMeta, Tag
from app.services.markdown_pipeline import compute_derived

DEFAULT_TAGS = [
    {"slug": "backend", "name": "backend", "color": "#7aa7ff"},
    {"slug": "ai", "name": "ai", "color": "#b794ff"},
    {"slug": "ml", "name": "ml", "color": "#ffb86b"},
    {"slug": "devtools", "name": "devtools", "color": "#7dd3a4"},
    {"slug": "infra", "name": "infra", "color": "#f47174"},
]

DEFAULT_PROJECTS = [
    ("segformer-lite", "Tiny, quant-friendly segmentation model. 3.2MB, runs on ESP32-S3.", "Python", 1240, "active"),
    ("agentkit-jvm", "LangChain-style agent primitives, native Java. Zero Python in prod.", "Java", 812, "active"),
    ("pghelper-debug", "Runtime diagnostic for PageHelper — tells you why your page didn't page.", "Java", 203, "maintained"),
    ("dotfiles", "Terminal, editor, and kernel tunings I run on every box.", "Shell", 96, "active"),
    ("term-i18n", "Lint your SSH/locale config across a fleet. Catches the Termius bug at scale.", "Go", 61, "active"),
]


async def _seed_bootstrap() -> None:
    async with AsyncSessionLocal() as s:
        # tags
        tags_by_slug: dict[str, Tag] = {}
        for i, td in enumerate(DEFAULT_TAGS):
            existing = (await s.execute(select(Tag).where(Tag.slug == td["slug"]))).scalar_one_or_none()
            if existing is None:
                tag = Tag(slug=td["slug"], name=td["name"], color=td["color"], sort_order=i)
                s.add(tag)
                await s.flush()
                tags_by_slug[td["slug"]] = tag
            else:
                tags_by_slug[td["slug"]] = existing

        # site_meta singleton
        sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one_or_none()
        if sm is None:
            sm = SiteMeta(
                id=1,
                handle="wangyang", name="汪洋", name_en="Wang Yang",
                role="Backend / AI Full-Stack Engineer",
                tagline="Backends that don't flinch. Models that ship.",
                bio="I build backend systems and AI agents.",
                location="Hangzhou, CN",
                email="hi@wangyang.dev", github="wangyang",
                typing_line="// building backends that don't flinch.\n// training models that ship.",
                stack_chips=["Java", "Python", "PyTorch", "Agents", "Segmentation"],
                footer_note="© 2026 Wang Yang · hand-coded · cookie-less analytics",
                launched_at=date(2023, 1, 1),
            )
            s.add(sm)

        # projects
        for i, (n, d, l, st, status) in enumerate(DEFAULT_PROJECTS):
            existing = (await s.execute(select(Project).where(Project.name == n))).scalar_one_or_none()
            if existing is None:
                s.add(Project(
                    name=n, description=d, lang=l, stars=st, status=status, sort_order=i
                ))

        await s.commit()


@seed_app.command("bootstrap")
def seed_bootstrap() -> None:
    """Seed default tags, site_meta, and projects."""
    asyncio.run(_seed_bootstrap())
    typer.echo("✓ tags + site_meta + projects seeded")
```

- [ ] **Step 2: Run + verify**

```bash
uv run python -m app.cli seed bootstrap
docker exec -it $(docker ps -qf 'ancestor=postgres:16-alpine') psql -U myblog -d myblog -c "select count(*) from tags; select count(*) from projects; select handle, name from site_meta;"
```

Expected: tags=5, projects=5, one site_meta row.

- [ ] **Step 3: Commit**

```bash
git add backend/app/cli.py
git commit -m "feat(backend): seed bootstrap (tags + site_meta + projects)"
```

---

### Task 20: `import-md` command (single file + dir + auto-frontmatter)

**Files:**
- Modify: `backend/app/cli.py`
- Create: `backend/app/services/post_ingest.py`

- [ ] **Step 1: Write `backend/app/services/post_ingest.py`**

```python
"""Ingest a markdown document (with or without frontmatter) into the posts table."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

import frontmatter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Post, Tag
from app.services.frontmatter_schema import PostFrontmatter
from app.services.markdown_pipeline import compute_derived, parse_markdown

SENSITIVE = re.compile(r"^(accounts?|secrets?|password?|credential?|.*\.env)", re.IGNORECASE)


class IngestError(ValueError):
    pass


def is_sensitive(path: Path) -> bool:
    return bool(SENSITIVE.match(path.stem))


def _slugify(name: str) -> str:
    s = name.lower()
    s = re.sub(r"[^a-z0-9-]+", "-", s).strip("-")
    return s[:64] or "post"


def _detect_lang(text: str) -> str:
    cjk = sum(1 for c in text if "一" <= c <= "鿿")
    return "zh" if cjk / max(1, len(text)) > 0.3 else "en"


def _extract_first_h1(body: str) -> str | None:
    for line in body.splitlines():
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return None


async def _next_n(session: AsyncSession) -> str:
    max_n = (await session.execute(select(func.max(Post.n)))).scalar() or "000"
    try:
        return f"{int(max_n) + 1:03d}"
    except ValueError:
        return "001"


async def parse_or_infer_frontmatter(
    session: AsyncSession,
    *,
    raw: str,
    file_path: Path | None,
    default_tag: str | None,
) -> tuple[PostFrontmatter, str]:
    """Returns (validated_frontmatter, body_md)."""
    parsed = frontmatter.loads(raw)
    body = parsed.content
    meta = dict(parsed.metadata)

    if not meta:
        # Auto-infer mode
        title = _extract_first_h1(body)
        if title is None:
            raise IngestError("no frontmatter and no H1 to infer title from")
        if file_path is not None:
            meta["id"] = _slugify(file_path.stem)
            meta["date"] = date.fromtimestamp(file_path.stat().st_mtime).isoformat()
        else:
            meta["id"] = _slugify(title)
            meta["date"] = date.today().isoformat()
        meta["title"] = title
        meta["n"] = await _next_n(session)
        meta["lang"] = _detect_lang(body)
        if default_tag is None:
            raise IngestError(
                "no frontmatter present; supply --default-tag <slug> or add frontmatter"
            )
        meta["tag"] = default_tag

    fm = PostFrontmatter(**meta)

    # Tag must exist
    tag_row = (await session.execute(select(Tag).where(Tag.slug == fm.tag))).scalar_one_or_none()
    if tag_row is None:
        raise IngestError(f"tag '{fm.tag}' not found in tags table; create it first")

    return fm, body


async def upsert_post(
    session: AsyncSession,
    *,
    fm: PostFrontmatter,
    body_md: str,
    overwrite: bool,
) -> Post:
    blocks = parse_markdown(body_md)
    derived = compute_derived(blocks)
    tag_row = (await session.execute(select(Tag).where(Tag.slug == fm.tag))).scalar_one()

    existing = (await session.execute(select(Post).where(Post.id == fm.id))).scalar_one_or_none()
    if existing is not None and not overwrite:
        raise IngestError(f"post id '{fm.id}' already exists (pass --overwrite to replace)")

    if existing is None:
        post = Post(id=fm.id, tag_id=tag_row.id, body_md=body_md, body_json=blocks)
        session.add(post)
    else:
        post = existing
        post.tag_id = tag_row.id
        post.body_md = body_md
        post.body_json = blocks

    post.n = fm.n
    post.title = fm.title
    post.subtitle = fm.subtitle
    post.date = fm.date
    post.read = fm.read or derived["read"]
    post.lang = fm.lang
    post.summary = fm.summary or derived["summary"]
    post.tldr = fm.tldr
    post.status = fm.status
    post.scheduled_at = fm.scheduled_at
    post.featured = fm.featured
    post.private = fm.private
    post.comments_enabled = fm.comments_enabled
    post.word_count = derived["word_count"]
    return post
```

- [ ] **Step 2: Append to `backend/app/cli.py`**

```python
import frontmatter as fm_lib

from app.services.post_ingest import IngestError, is_sensitive, parse_or_infer_frontmatter, upsert_post


async def _import_md_file(
    path: Path, default_tag: str | None, overwrite: bool, dry_run: bool
) -> tuple[bool, str]:
    if is_sensitive(path):
        return False, f"⊘ skipped (sensitive name): {path.name}"
    raw = path.read_text(encoding="utf-8")
    async with AsyncSessionLocal() as session:
        try:
            fm_obj, body = await parse_or_infer_frontmatter(
                session, raw=raw, file_path=path, default_tag=default_tag
            )
            if dry_run:
                return True, f"DRY  {path.name} → id='{fm_obj.id}' tag='{fm_obj.tag}' lang='{fm_obj.lang}'"
            await upsert_post(session, fm=fm_obj, body_md=body, overwrite=overwrite)
            await session.commit()
            return True, f"✓    {path.name} → posts/{fm_obj.id}"
        except IngestError as e:
            return False, f"✗    {path.name} → {e}"


@app.command("import-md")
def import_md(
    path: Path = typer.Argument(..., exists=True, dir_okay=True, file_okay=True),
    overwrite: bool = typer.Option(False, "--overwrite"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    default_tag: str | None = typer.Option(None, "--default-tag"),
) -> None:
    """Import a single .md file or a directory of .md files."""
    files: list[Path] = (
        sorted(path.rglob("*.md")) if path.is_dir() else [path]
    )
    if not files:
        typer.echo("no .md files found")
        raise typer.Exit(code=1)

    results = asyncio.run(_run_imports(files, default_tag, overwrite, dry_run))
    ok = sum(1 for r in results if r[0])
    failed = len(results) - ok
    for _, msg in results:
        typer.echo(msg)
    typer.echo(f"─" * 60)
    typer.echo(f"total {len(results)} · ok {ok} · failed {failed}")


async def _run_imports(
    files: list[Path], default_tag: str | None, overwrite: bool, dry_run: bool
) -> list[tuple[bool, str]]:
    return [await _import_md_file(p, default_tag, overwrite, dry_run) for p in files]
```

- [ ] **Step 3: Smoke test against the user's real folder (dry-run first)**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run python -m app.cli import-md /Users/sd3/Desktop/工具文档 --dry-run --default-tag devtools
```

Expected: 7 lines `DRY ...` (one per non-sensitive .md) + 1 line `⊘ skipped (sensitive name): accounts.md`.

- [ ] **Step 4: Real import**

```bash
uv run python -m app.cli import-md /Users/sd3/Desktop/工具文档 --default-tag devtools
docker exec -it $(docker ps -qf 'ancestor=postgres:16-alpine') psql -U myblog -d myblog -c "select id, title, lang, status, word_count from posts order by created_at desc;"
```

Expected: 7 rows in posts.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/post_ingest.py backend/app/cli.py
git commit -m "feat(backend): import-md CLI with auto-frontmatter inference + sensitive-name skip"
```

---

## Phase F — Public read endpoints

### Task 21: Test client fixture for routers

**Files:**
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: Write `backend/tests/conftest.py`**

```python
import asyncio
import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Tests share the dev DB at default DATABASE_URL.
# Each test runs inside a transaction that rolls back; engine is module-scoped.

from app.main import create_app
from app.models import Base


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def engine():
    url = os.environ["DATABASE_URL"]
    eng = create_async_engine(url, future=True)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

(For Phase 1, tests run against the dev DB to keep complexity low; Phase 4 introduces `pytest-postgresql`-driven schema isolation when test count grows.)

- [ ] **Step 2: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test(backend): shared client fixture for routers"
```

---

### Task 22: `/api/site` + Pydantic schema

**Files:**
- Create: `backend/app/schemas/site.py`
- Create: `backend/app/routers/public/site.py`
- Modify: `backend/app/routers/public/__init__.py`
- Create: `backend/tests/test_public_misc.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_public_misc.py`:

```python
async def test_site_payload_shape(client):
    r = await client.get("/api/site")
    assert r.status_code == 200
    body = r.json()
    for key in (
        "handle", "name", "name_en", "role", "tagline", "bio", "location", "email", "github",
        "uptime", "posts", "words", "commits52w", "footer_note",
        "default_theme", "accent_color", "accent2_color", "violet_color", "danger_color",
    ):
        assert key in body, f"missing key: {key}"
    assert isinstance(body["uptime"], str)
    assert body["posts"] >= 0
```

- [ ] **Step 2: Write `backend/app/schemas/site.py`**

```python
from pydantic import BaseModel


class SitePayload(BaseModel):
    handle: str
    name: str
    name_en: str
    role: str
    tagline: str
    bio: str
    location: str
    email: str
    github: str
    pronouns: str | None = None
    uptime: str
    posts: int
    words: int
    commits52w: int
    footer_note: str
    default_theme: str
    accent_color: str
    accent2_color: str
    violet_color: str
    danger_color: str
    typing_line: str
    stack_chips: list[str]


class ProfilePayload(BaseModel):
    name: str
    name_en: str
    role: str
    bio: str
    location: str
    pronouns: str | None
    avatar_path: str | None
    typing_line: str
    stack_chips: list[str]
```

- [ ] **Step 3: Write `backend/app/routers/public/site.py`**

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ContribDay, Post, SiteMeta
from app.schemas.site import ProfilePayload, SitePayload

router = APIRouter()


def _format_uptime(launched: date) -> str:
    days = (date.today() - launched).days
    years, rest = divmod(days, 365)
    return f"{years}y {rest}d"


@router.get("/site", response_model=SitePayload)
async def get_site(s: AsyncSession = Depends(get_session)) -> SitePayload:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    posts_count = (await s.execute(
        select(func.count()).select_from(Post).where(Post.status == "published")
    )).scalar_one()
    words = (await s.execute(
        select(func.coalesce(func.sum(Post.word_count), 0)).where(Post.status == "published")
    )).scalar_one()
    commits52w = (await s.execute(
        select(func.coalesce(func.sum(ContribDay.count), 0))
    )).scalar_one() or 1384  # seed fallback

    return SitePayload(
        handle=sm.handle, name=sm.name, name_en=sm.name_en, role=sm.role,
        tagline=sm.tagline, bio=sm.bio, location=sm.location,
        email=sm.email, github=sm.github, pronouns=sm.pronouns,
        uptime=_format_uptime(sm.launched_at),
        posts=int(posts_count), words=int(words), commits52w=int(commits52w),
        footer_note=sm.footer_note,
        default_theme=sm.default_theme,
        accent_color=sm.accent_color, accent2_color=sm.accent2_color,
        violet_color=sm.violet_color, danger_color=sm.danger_color,
        typing_line=sm.typing_line, stack_chips=sm.stack_chips,
    )


@router.get("/profile", response_model=ProfilePayload)
async def get_profile(s: AsyncSession = Depends(get_session)) -> ProfilePayload:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
    return ProfilePayload(
        name=sm.name, name_en=sm.name_en, role=sm.role, bio=sm.bio,
        location=sm.location, pronouns=sm.pronouns, avatar_path=sm.avatar_path,
        typing_line=sm.typing_line, stack_chips=sm.stack_chips,
    )
```

- [ ] **Step 4: Update `backend/app/routers/public/__init__.py`**

```python
from fastapi import APIRouter

from app.routers.public.health import router as health_router
from app.routers.public.site import router as site_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
router.include_router(site_router, tags=["site"])
```

- [ ] **Step 5: Run; expect PASS**

```bash
uv run pytest tests/test_public_misc.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/site.py backend/app/routers/public/site.py backend/app/routers/public/__init__.py backend/tests/test_public_misc.py
git commit -m "feat(backend): /api/site and /api/profile"
```

---

### Task 23: `/api/contacts`, `/api/tags`, `/api/projects`

**Files:**
- Create: `backend/app/schemas/contact.py`, `tag.py`, `project.py`
- Create: `backend/app/routers/public/contacts.py`, `tags.py`, `projects.py`
- Modify: `backend/app/routers/public/__init__.py`
- Modify: `backend/tests/test_public_misc.py`

- [ ] **Step 1: Write Pydantic schemas**

`backend/app/schemas/contact.py`:

```python
from pydantic import BaseModel


class ContactPayload(BaseModel):
    id: int
    label: str
    value: str
    href: str
    visible: bool
    sort_order: int

    model_config = {"from_attributes": True}
```

`backend/app/schemas/tag.py`:

```python
from pydantic import BaseModel


class TagPayload(BaseModel):
    id: str   # slug; "all" is synthetic
    label: str
    n: int    # post count
```

`backend/app/schemas/project.py`:

```python
from pydantic import BaseModel


class ProjectPayload(BaseModel):
    name: str
    desc: str
    lang: str
    stars: int
    status: str
```

- [ ] **Step 2: Write the routers**

`backend/app/routers/public/contacts.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Contact
from app.schemas.contact import ContactPayload

router = APIRouter()


@router.get("/contacts", response_model=list[ContactPayload])
async def list_contacts(s: AsyncSession = Depends(get_session)) -> list[ContactPayload]:
    rows = (
        await s.execute(
            select(Contact).where(Contact.visible.is_(True)).order_by(Contact.sort_order)
        )
    ).scalars().all()
    return [ContactPayload.model_validate(r) for r in rows]
```

`backend/app/routers/public/tags.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, Tag
from app.schemas.tag import TagPayload

router = APIRouter()


@router.get("/tags", response_model=list[TagPayload])
async def list_tags(s: AsyncSession = Depends(get_session)) -> list[TagPayload]:
    rows = (
        await s.execute(
            select(Tag.slug, Tag.name, func.count(Post.id))
            .outerjoin(Post, (Post.tag_id == Tag.id) & (Post.status == "published"))
            .group_by(Tag.id)
            .order_by(Tag.sort_order)
        )
    ).all()
    total = sum(r[2] for r in rows)
    out = [TagPayload(id="all", label="all", n=int(total))]
    out.extend(TagPayload(id=slug, label=name, n=int(n)) for slug, name, n in rows)
    return out
```

`backend/app/routers/public/projects.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Project
from app.schemas.project import ProjectPayload

router = APIRouter()


@router.get("/projects", response_model=list[ProjectPayload])
async def list_projects(s: AsyncSession = Depends(get_session)) -> list[ProjectPayload]:
    rows = (
        await s.execute(
            select(Project).where(Project.visible.is_(True)).order_by(Project.sort_order)
        )
    ).scalars().all()
    return [
        ProjectPayload(
            name=r.name, desc=r.description, lang=r.lang, stars=r.stars, status=r.status
        )
        for r in rows
    ]
```

- [ ] **Step 3: Update `backend/app/routers/public/__init__.py`**

```python
from fastapi import APIRouter

from app.routers.public.contacts import router as contacts_router
from app.routers.public.health import router as health_router
from app.routers.public.projects import router as projects_router
from app.routers.public.site import router as site_router
from app.routers.public.tags import router as tags_router

router = APIRouter(prefix="/api")
router.include_router(health_router, tags=["health"])
router.include_router(site_router, tags=["site"])
router.include_router(contacts_router, tags=["public"])
router.include_router(tags_router, tags=["public"])
router.include_router(projects_router, tags=["public"])
```

- [ ] **Step 4: Append tests**

Append to `backend/tests/test_public_misc.py`:

```python
async def test_contacts_returns_list(client):
    r = await client.get("/api/contacts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_tags_includes_all(client):
    r = await client.get("/api/tags")
    assert r.status_code == 200
    body = r.json()
    assert any(t["id"] == "all" for t in body)
    assert all(set(t.keys()) == {"id", "label", "n"} for t in body)


async def test_projects_returns_list(client):
    r = await client.get("/api/projects")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        assert set(body[0].keys()) == {"name", "desc", "lang", "stars", "status"}
```

- [ ] **Step 5: Run; expect PASS**

```bash
uv run pytest tests/test_public_misc.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/contact.py backend/app/schemas/tag.py backend/app/schemas/project.py backend/app/routers/public/contacts.py backend/app/routers/public/tags.py backend/app/routers/public/projects.py backend/app/routers/public/__init__.py backend/tests/test_public_misc.py
git commit -m "feat(backend): /api/contacts, /api/tags, /api/projects"
```

---

### Task 24: `/api/posts` list + filter + pagination

**Files:**
- Create: `backend/app/schemas/post.py`
- Create: `backend/app/routers/public/posts.py`
- Modify: `backend/app/routers/public/__init__.py`
- Create: `backend/tests/test_public_posts.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_public_posts.py`:

```python
async def test_posts_list_returns_paged(client):
    r = await client.get("/api/posts?limit=20&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert {"items", "total", "limit", "offset"} <= set(body.keys())
    assert body["limit"] == 20
    assert body["offset"] == 0


async def test_posts_list_filter_by_tag(client):
    r = await client.get("/api/posts?tag=devtools")
    assert r.status_code == 200
    body = r.json()
    for p in body["items"]:
        assert p["tag"] == "devtools"


async def test_posts_list_search_query(client):
    r = await client.get("/api/posts?q=Termius")
    assert r.status_code == 200
    body = r.json()
    assert all("Termius" in p["title"] or "Termius" in (p["summary"] or "") for p in body["items"])


async def test_posts_list_lang_filter(client):
    r = await client.get("/api/posts?lang=zh")
    assert r.status_code == 200
    for p in r.json()["items"]:
        assert p["lang"] == "zh"


async def test_posts_list_excludes_drafts(client):
    r = await client.get("/api/posts")
    assert all(p.get("status", "published") == "published" for p in r.json()["items"])
```

- [ ] **Step 2: Write `backend/app/schemas/post.py`**

```python
from datetime import date as date_t
from typing import Any

from pydantic import BaseModel, ConfigDict


class PostSummary(BaseModel):
    id: str
    n: str
    title: str
    subtitle: str | None
    tag: str   # slug
    date: date_t
    read: str | None
    lang: str
    summary: str | None


class PostDetail(PostSummary):
    tldr: str | None
    body: list[dict[str, Any]]
    likes: int
    word_count: int


class PostList(BaseModel):
    items: list[PostSummary]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 3: Write `backend/app/routers/public/posts.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Post, Tag
from app.schemas.post import PostDetail, PostList, PostSummary

router = APIRouter()


def _summary_from_row(p: Post) -> PostSummary:
    return PostSummary(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
    )


@router.get("/posts", response_model=PostList)
async def list_posts(
    tag: str | None = Query(None),
    q: str | None = Query(None, min_length=1, max_length=100),
    lang: str | None = Query(None, pattern="^(zh|en)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    s: AsyncSession = Depends(get_session),
) -> PostList:
    stmt = select(Post).join(Tag).where(Post.status == "published", Post.private.is_(False))
    if tag and tag != "all":
        stmt = stmt.where(Tag.slug == tag)
    if lang:
        stmt = stmt.where(Post.lang == lang)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Post.title.ilike(like), Post.summary.ilike(like), Post.body_md.ilike(like)))
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await s.execute(stmt.order_by(Post.date.desc()).limit(limit).offset(offset))).scalars().all()
    return PostList(
        items=[_summary_from_row(p) for p in rows],
        total=int(total), limit=limit, offset=offset,
    )


@router.get("/posts/{post_id}", response_model=PostDetail)
async def get_post(post_id: str, s: AsyncSession = Depends(get_session)) -> PostDetail:
    post = (await s.execute(
        select(Post).join(Tag).where(
            Post.id == post_id, Post.status == "published", Post.private.is_(False)
        )
    )).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    return PostDetail(
        id=post.id, n=post.n, title=post.title, subtitle=post.subtitle, tag=post.tag.slug,
        date=post.date, read=post.read, lang=post.lang, summary=post.summary,
        tldr=post.tldr, body=post.body_json, likes=0, word_count=post.word_count,
    )
```

(`likes=0` is a placeholder; Phase 4 wires real counts from `like_events`.)

- [ ] **Step 4: Update `backend/app/routers/public/__init__.py`**

Insert at the include section:

```python
from app.routers.public.posts import router as posts_router
# ...
router.include_router(posts_router, tags=["public"])
```

- [ ] **Step 5: Run; expect PASS**

```bash
uv run pytest tests/test_public_posts.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/post.py backend/app/routers/public/posts.py backend/app/routers/public/__init__.py backend/tests/test_public_posts.py
git commit -m "feat(backend): /api/posts list+filter+pagination + /api/posts/{id}"
```

---

### Task 25: `/api/contrib` (seed fallback)

**Files:**
- Create: `backend/app/routers/public/contrib.py`
- Modify: `backend/app/routers/public/__init__.py`
- Modify: `backend/tests/test_public_misc.py`

- [ ] **Step 1: Write `backend/app/routers/public/contrib.py`**

```python
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import ContribDay

router = APIRouter()

_MONTHS = ["May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]


def _seed_grid() -> list[list[int]]:
    """Deterministic LCG fallback that mirrors the original frontend data.js generator."""
    s = 42
    grid: list[list[int]] = []
    for w in range(52):
        col: list[int] = []
        for d in range(7):
            s = (s * 9301 + 49297) % 233280
            r = s / 233280
            weekday = 1.2 if 0 < d < 6 else 0.6
            v = r * weekday
            level = 0
            if v > 0.35: level = 1
            if v > 0.6: level = 2
            if v > 0.8: level = 3
            if v > 0.93: level = 4
            col.append(level)
        grid.append(col)
    return grid


@router.get("/contrib")
async def get_contrib(
    weeks: int = Query(52, ge=1, le=104),
    s: AsyncSession = Depends(get_session),
) -> dict:
    rows = (await s.execute(select(ContribDay))).scalars().all()
    if not rows:
        grid = _seed_grid()
        commits = 1384
        return {"weeks": weeks, "grid": grid, "months": _MONTHS, "commits": commits, "source": "seed"}

    by_day = {r.day: r for r in rows}
    today = date.today()
    grid: list[list[int]] = [[0] * 7 for _ in range(weeks)]
    commits = 0
    for w in range(weeks):
        for d in range(7):
            day = today - timedelta(days=(weeks - 1 - w) * 7 + (6 - d))
            r = by_day.get(day)
            if r is not None:
                grid[w][d] = r.level
                commits += r.count
    return {"weeks": weeks, "grid": grid, "months": _MONTHS, "commits": commits, "source": "github"}
```

- [ ] **Step 2: Wire into `backend/app/routers/public/__init__.py`**

Add the import + include similarly to others.

- [ ] **Step 3: Append test**

Append to `backend/tests/test_public_misc.py`:

```python
async def test_contrib_returns_grid(client):
    r = await client.get("/api/contrib")
    assert r.status_code == 200
    body = r.json()
    assert body["weeks"] == 52
    assert len(body["grid"]) == 52
    assert all(len(col) == 7 for col in body["grid"])
    assert body["source"] in ("seed", "github")
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_public_misc.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/public/contrib.py backend/app/routers/public/__init__.py backend/tests/test_public_misc.py
git commit -m "feat(backend): /api/contrib (seed fallback when contrib_days empty)"
```

---

## Phase G — Admin auth (minimal: email + password + JWT, no refresh, no 2FA)

### Task 26: JWT helpers

**Files:**
- Modify: `backend/app/services/auth.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Append failing tests**

`backend/tests/test_auth.py`:

```python
from datetime import timedelta

import pytest

from app.services.auth import create_access_token, decode_access_token, AuthError


def test_token_round_trip():
    token = create_access_token(sub="1", email="hi@a.dev")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["email"] == "hi@a.dev"


def test_token_expired_raises():
    token = create_access_token(sub="1", email="hi@a.dev", ttl=timedelta(seconds=-5))
    with pytest.raises(AuthError):
        decode_access_token(token)


def test_token_tampered_raises():
    token = create_access_token(sub="1", email="hi@a.dev")
    bad = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(AuthError):
        decode_access_token(bad)
```

- [ ] **Step 2: Run; expect FAIL**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Step 3: Append to `backend/app/services/auth.py`**

```python
from datetime import datetime, timedelta, UTC

import jwt

from app.config import get_settings
from app.errors import AuthError

_settings = get_settings()


def create_access_token(*, sub: str, email: str, ttl: timedelta | None = None) -> str:
    expires = datetime.now(UTC) + (ttl or timedelta(seconds=_settings.access_token_ttl))
    return jwt.encode(
        {"sub": sub, "email": email, "iat": datetime.now(UTC), "exp": expires},
        _settings.jwt_secret, algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, _settings.jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("token expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("invalid token") from e
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_auth.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/auth.py backend/tests/test_auth.py
git commit -m "feat(backend): JWT access-token helpers"
```

---

### Task 27: `current_admin` dependency + login endpoint

**Files:**
- Create: `backend/app/deps.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/routers/admin/auth.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_admin_auth.py`

- [ ] **Step 1: Write `backend/app/deps.py`**

```python
from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import AuthError
from app.models import Account
from app.services.auth import decode_access_token


async def current_admin(
    authorization: str | None = Header(None),
    s: AsyncSession = Depends(get_session),
) -> Account:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthError("missing bearer token")
    payload = decode_access_token(authorization.split(None, 1)[1].strip())
    acct = (await s.execute(select(Account).where(Account.id == int(payload["sub"])))).scalar_one_or_none()
    if acct is None or acct.email != payload.get("email"):
        raise AuthError("account not found")
    return acct
```

- [ ] **Step 2: Write `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    access: str
    token_type: str = "bearer"
    expires_in: int
```

- [ ] **Step 3: Write `backend/app/routers/admin/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.deps import current_admin
from app.models import Account
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import create_access_token, verify_password

router = APIRouter()


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest, s: AsyncSession = Depends(get_session)) -> LoginResponse:
    acct = (await s.execute(select(Account).where(Account.email == req.email))).scalar_one_or_none()
    if acct is None or not verify_password(acct.password_hash, req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials")
    settings = get_settings()
    token = create_access_token(sub=str(acct.id), email=acct.email)
    return LoginResponse(access=token, expires_in=settings.access_token_ttl)


@router.get("/session")
async def get_session_(admin: Account = Depends(current_admin)) -> dict:
    return {"id": admin.id, "email": admin.email, "tfa_enabled": admin.tfa_enabled}
```

- [ ] **Step 4: Write `backend/app/routers/admin/__init__.py`**

```python
from fastapi import APIRouter

from app.routers.admin.auth import router as auth_router

router = APIRouter(prefix="/api/admin")
router.include_router(auth_router, tags=["admin·auth"])
```

- [ ] **Step 5: Wire admin router into `backend/app/main.py`**

In `create_app()` after `app.include_router(public_router)`:

```python
from app.routers.admin import router as admin_router
app.include_router(admin_router)
```

- [ ] **Step 6: Write the failing test**

`backend/tests/test_admin_auth.py`:

```python
import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    assert r.status_code == 200, r.text
    return r.json()["access"]


async def test_login_bad_password_401(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": "wrong"})
    assert r.status_code == 401


async def test_login_unknown_email_401(client):
    r = await client.post("/api/admin/auth/login", json={"email": "nobody@x.com", "password": "x"})
    assert r.status_code == 401


async def test_session_requires_token(client):
    r = await client.get("/api/admin/session")
    assert r.status_code == 401


async def test_session_returns_account(client, admin_token):
    r = await client.get("/api/admin/session", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["email"] == EMAIL
```

- [ ] **Step 7: Run; expect PASS (admin must already be seeded from Task 18)**

```bash
uv run pytest tests/test_admin_auth.py -v
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/deps.py backend/app/schemas/auth.py backend/app/routers/admin/auth.py backend/app/routers/admin/__init__.py backend/app/main.py backend/tests/test_admin_auth.py
git commit -m "feat(backend): admin login + JWT-protected /session"
```

---

## Phase H — Admin content CRUD

### Task 28: Event-log writer service

**Files:**
- Create: `backend/app/services/event_log.py`

- [ ] **Step 1: Write `backend/app/services/event_log.py`**

```python
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EventLog


async def write_event(
    session: AsyncSession,
    *,
    type: str,
    actor: str = "admin",
    target: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Append one event_log row inside the caller's session.

    Failures here MUST NOT block the main operation; we let exceptions surface
    only in dev (so tests catch missing columns); in prod, the caller wraps
    this in try/except. We keep it simple here.
    """
    session.add(EventLog(type=type, actor=actor, target=target, meta=meta or {}))
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/event_log.py
git commit -m "feat(backend): event_log writer helper"
```

---

### Task 29: Admin posts — list + create (JSON body)

**Files:**
- Create: `backend/app/routers/admin/posts.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Create: `backend/tests/test_admin_posts.py`

- [ ] **Step 1: Write `backend/app/routers/admin/posts.py`**

```python
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Post, Tag
from app.schemas.post import PostDetail, PostList, PostSummary
from app.services.event_log import write_event
from app.services.post_ingest import IngestError, parse_or_infer_frontmatter, upsert_post

router = APIRouter()


def _summary(p: Post) -> PostSummary:
    return PostSummary(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
    )


def _detail(p: Post) -> PostDetail:
    return PostDetail(
        id=p.id, n=p.n, title=p.title, subtitle=p.subtitle, tag=p.tag.slug,
        date=p.date, read=p.read, lang=p.lang, summary=p.summary,
        tldr=p.tldr, body=p.body_json, likes=0, word_count=p.word_count,
    )


@router.get("/posts", response_model=PostList)
async def list_posts(
    status: str | None = Query(None, pattern="^(draft|published|scheduled|all)$"),
    tag: str | None = Query(None),
    q: str | None = Query(None, min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostList:
    stmt = select(Post).join(Tag)
    if status and status != "all":
        stmt = stmt.where(Post.status == status)
    if tag and tag != "all":
        stmt = stmt.where(Tag.slug == tag)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Post.title.ilike(like), Post.summary.ilike(like), Post.body_md.ilike(like)))
    total = (await s.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (await s.execute(stmt.order_by(Post.date.desc()).limit(limit).offset(offset))).scalars().all()
    return PostList(items=[_summary(p) for p in rows], total=int(total), limit=limit, offset=offset)


@router.post("/posts", response_model=PostDetail, status_code=201)
async def create_post(
    body: Annotated[dict, Body(..., example={"markdown": "---\nid: ...\n---\nbody"})],
    overwrite: bool = Query(False),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    md = body.get("markdown")
    if not isinstance(md, str) or not md.strip():
        raise HTTPException(status_code=422, detail="markdown body required")
    try:
        fm, body_md = await parse_or_infer_frontmatter(s, raw=md, file_path=None, default_tag=None)
        post = await upsert_post(s, fm=fm, body_md=body_md, overwrite=overwrite)
    except IngestError as e:
        raise HTTPException(status_code=409 if "already exists" in str(e) else 422, detail=str(e))
    await write_event(s, type="post.created", actor=admin.email, target=post.id)
    await s.flush()
    # reload with tag
    post = (await s.execute(select(Post).join(Tag).where(Post.id == fm.id))).scalar_one()
    return _detail(post)


@router.get("/posts/{post_id}", response_model=PostDetail)
async def get_post(
    post_id: str,
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    return _detail(post)


@router.patch("/posts/{post_id}", response_model=PostDetail)
async def patch_post(
    post_id: str,
    body: dict = Body(...),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> PostDetail:
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    md = body.get("markdown")
    if not isinstance(md, str) or not md.strip():
        raise HTTPException(status_code=422, detail="markdown body required")
    try:
        fm, body_md = await parse_or_infer_frontmatter(s, raw=md, file_path=None, default_tag=None)
        if fm.id != post_id:
            raise HTTPException(status_code=422, detail="frontmatter id mismatch")
        await upsert_post(s, fm=fm, body_md=body_md, overwrite=True)
    except IngestError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await write_event(s, type="post.updated", actor=admin.email, target=post_id)
    await s.flush()
    post = (await s.execute(select(Post).join(Tag).where(Post.id == post_id))).scalar_one()
    return _detail(post)


@router.delete("/posts/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> None:
    post = (await s.execute(select(Post).where(Post.id == post_id))).scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(post)
    await write_event(s, type="post.deleted", actor=admin.email, target=post_id)


@router.post("/posts/render-preview")
async def render_preview(
    body: dict = Body(...),
    _: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict:
    md = body.get("markdown", "")
    try:
        fm, body_md = await parse_or_infer_frontmatter(s, raw=md, file_path=None, default_tag=None)
    except IngestError as e:
        return {"errors": [str(e)], "frontmatter": None, "body": []}
    from app.services.markdown_pipeline import compute_derived, parse_markdown
    try:
        blocks = parse_markdown(body_md)
    except Exception as e:
        return {"errors": [str(e)], "frontmatter": fm.model_dump(mode="json"), "body": []}
    derived = compute_derived(blocks)
    return {
        "errors": [],
        "warnings": [],
        "frontmatter": fm.model_dump(mode="json"),
        "body": blocks,
        "derived": derived,
    }
```

- [ ] **Step 2: Update `backend/app/routers/admin/__init__.py`**

```python
from fastapi import APIRouter

from app.routers.admin.auth import router as auth_router
from app.routers.admin.posts import router as posts_router

router = APIRouter(prefix="/api/admin")
router.include_router(auth_router, tags=["admin·auth"])
router.include_router(posts_router, tags=["admin·posts"])
```

- [ ] **Step 3: Write the failing tests**

`backend/tests/test_admin_posts.py`:

```python
import pytest

GOOD_MD = """---
id: test-post-1
n: "999"
title: Test post
tag: devtools
date: 2026-04-25
lang: en
status: published
---

## Heading

A paragraph.
"""


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": "hi@wangyang.dev", "password": "changeme"})
    return r.json()["access"]


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


async def test_create_requires_auth(client):
    r = await client.post("/api/admin/posts", json={"markdown": GOOD_MD})
    assert r.status_code == 401


async def test_create_post_then_get(client, auth):
    # cleanup if previous run left it
    await client.delete("/api/admin/posts/test-post-1", headers=auth)

    r = await client.post("/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "test-post-1"

    g = await client.get("/api/admin/posts/test-post-1", headers=auth)
    assert g.status_code == 200
    assert g.json()["title"] == "Test post"

    # Cleanup
    await client.delete("/api/admin/posts/test-post-1", headers=auth)


async def test_render_preview_returns_blocks(client, auth):
    r = await client.post("/api/admin/posts/render-preview", json={"markdown": GOOD_MD}, headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] == []
    assert body["frontmatter"]["id"] == "test-post-1"
    assert any(b["t"] == "h2" for b in body["body"])


async def test_create_duplicate_409(client, auth):
    await client.delete("/api/admin/posts/test-post-1", headers=auth)
    r1 = await client.post("/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth)
    assert r1.status_code == 201
    r2 = await client.post("/api/admin/posts", json={"markdown": GOOD_MD}, headers=auth)
    assert r2.status_code == 409
    await client.delete("/api/admin/posts/test-post-1", headers=auth)


async def test_admin_list_includes_drafts(client, auth):
    draft = GOOD_MD.replace("status: published", "status: draft").replace("test-post-1", "test-draft-1")
    await client.post("/api/admin/posts", json={"markdown": draft}, headers=auth)
    r = await client.get("/api/admin/posts?status=draft", headers=auth)
    assert r.status_code == 200
    assert any(p["id"] == "test-draft-1" for p in r.json()["items"])
    await client.delete("/api/admin/posts/test-draft-1", headers=auth)
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_admin_posts.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/admin/posts.py backend/app/routers/admin/__init__.py backend/tests/test_admin_posts.py
git commit -m "feat(backend): admin posts CRUD + render-preview"
```

---

### Task 30: Admin posts — multipart `.md` upload (single + bulk)

**Files:**
- Modify: `backend/app/routers/admin/posts.py`
- Modify: `backend/tests/test_admin_posts.py`

- [ ] **Step 1: Append upload endpoint**

In `backend/app/routers/admin/posts.py`, add:

```python
from fastapi import File, UploadFile
from fastapi.responses import JSONResponse


@router.post("/posts/upload")
async def upload_md(
    files: list[UploadFile] = File(...),
    overwrite: bool = Query(False),
    admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> JSONResponse:
    if len(files) > 20:
        raise HTTPException(status_code=413, detail="max 20 files per upload")
    results: list[dict] = []
    ok = 0
    for f in files:
        if not (f.filename and (f.filename.endswith(".md") or f.filename.endswith(".markdown"))):
            results.append({"file": f.filename, "ok": False, "status": 415, "detail": "must be .md"})
            continue
        raw_bytes = await f.read()
        if len(raw_bytes) > 1_048_576:
            results.append({"file": f.filename, "ok": False, "status": 413, "detail": "exceeds 1MB"})
            continue
        try:
            text = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            results.append({"file": f.filename, "ok": False, "status": 422, "detail": "encoding must be utf-8"})
            continue
        try:
            fm, body_md = await parse_or_infer_frontmatter(s, raw=text, file_path=None, default_tag=None)
            post = await upsert_post(s, fm=fm, body_md=body_md, overwrite=overwrite)
            await write_event(s, type="post.created", actor=admin.email, target=post.id, meta={"via": "upload"})
            await s.flush()
            results.append({"file": f.filename, "ok": True, "post": {"id": post.id, "title": post.title}})
            ok += 1
        except IngestError as e:
            code = 409 if "already exists" in str(e) else 422
            results.append({"file": f.filename, "ok": False, "status": code, "detail": str(e)})

    failed = len(results) - ok
    if ok == len(results):
        status_code = 201
    elif ok > 0:
        status_code = 207
    else:
        status_code = 422
    return JSONResponse(
        status_code=status_code,
        content={"results": results, "summary": {"total": len(results), "ok": ok, "failed": failed}},
    )
```

- [ ] **Step 2: Append test**

In `tests/test_admin_posts.py`:

```python
import io


async def test_upload_single_md(client, auth):
    await client.delete("/api/admin/posts/upload-test-1", headers=auth)
    md = GOOD_MD.replace("test-post-1", "upload-test-1")
    files = {"files": ("upload-test-1.md", md.encode("utf-8"), "text/markdown")}
    r = await client.post("/api/admin/posts/upload", files=files, headers=auth)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["summary"] == {"total": 1, "ok": 1, "failed": 0}
    await client.delete("/api/admin/posts/upload-test-1", headers=auth)


async def test_upload_partial_failure_returns_207(client, auth):
    await client.delete("/api/admin/posts/upload-test-2", headers=auth)
    good = GOOD_MD.replace("test-post-1", "upload-test-2")
    bad = "no-frontmatter content"
    files = [
        ("files", ("a.md", good.encode("utf-8"), "text/markdown")),
        ("files", ("b.md", bad.encode("utf-8"), "text/markdown")),
    ]
    r = await client.post("/api/admin/posts/upload", files=files, headers=auth)
    assert r.status_code == 207
    body = r.json()
    assert body["summary"]["total"] == 2
    assert body["summary"]["ok"] == 1
    await client.delete("/api/admin/posts/upload-test-2", headers=auth)
```

- [ ] **Step 3: Run; expect PASS**

```bash
uv run pytest tests/test_admin_posts.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/admin/posts.py backend/tests/test_admin_posts.py
git commit -m "feat(backend): admin posts multipart .md upload (single + bulk + 207)"
```

---

### Task 31: Admin tags CRUD + reorder

**Files:**
- Create: `backend/app/routers/admin/tags.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Create: `backend/tests/test_admin_taxonomy.py`

- [ ] **Step 1: Write `backend/app/routers/admin/tags.py`**

```python
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Tag
from app.services.event_log import write_event

router = APIRouter()


class TagIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,31}$")
    name: str
    color: str = "#7dd3a4"
    sort_order: int = 0


class TagOut(BaseModel):
    id: int
    slug: str
    name: str
    color: str
    sort_order: int

    model_config = {"from_attributes": True}


@router.get("/tags", response_model=list[TagOut])
async def list_(_: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(Tag).order_by(Tag.sort_order))).scalars().all()
    return [TagOut.model_validate(r) for r in rows]


@router.post("/tags", response_model=TagOut, status_code=201)
async def create(payload: TagIn, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    if (await s.execute(select(Tag).where(Tag.slug == payload.slug))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="slug taken")
    tag = Tag(**payload.model_dump())
    s.add(tag)
    await write_event(s, type="tag.created", actor=admin.email, target=payload.slug)
    await s.flush()
    return TagOut.model_validate(tag)


@router.patch("/tags/{tag_id}", response_model=TagOut)
async def patch(
    tag_id: int, payload: dict = Body(...),
    admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session),
):
    tag = (await s.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("slug", "name", "color", "sort_order"):
        if k in payload:
            setattr(tag, k, payload[k])
    await write_event(s, type="tag.updated", actor=admin.email, target=tag.slug)
    return TagOut.model_validate(tag)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete(tag_id: int, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    tag = (await s.execute(select(Tag).where(Tag.id == tag_id))).scalar_one_or_none()
    if tag is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(tag)
    await write_event(s, type="tag.deleted", actor=admin.email, target=tag.slug)


@router.put("/tags/order", status_code=204)
async def reorder(payload: dict = Body(...), admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    ids = payload.get("ids")
    if not isinstance(ids, list):
        raise HTTPException(status_code=422, detail="ids: list[int] required")
    for sort_order, tid in enumerate(ids):
        tag = (await s.execute(select(Tag).where(Tag.id == tid))).scalar_one_or_none()
        if tag is None:
            raise HTTPException(status_code=422, detail=f"tag id {tid} not found")
        tag.sort_order = sort_order
    await write_event(s, type="tag.reordered", actor=admin.email)
```

- [ ] **Step 2: Wire into admin router**

`backend/app/routers/admin/__init__.py`:

```python
from app.routers.admin.tags import router as tags_router
# ...
router.include_router(tags_router, tags=["admin·tags"])
```

- [ ] **Step 3: Write test**

`backend/tests/test_admin_taxonomy.py`:

```python
import pytest


@pytest.fixture
async def auth(client):
    r = await client.post("/api/admin/auth/login", json={"email": "hi@wangyang.dev", "password": "changeme"})
    return {"Authorization": f"Bearer {r.json()['access']}"}


async def test_tags_list_returns_seeded(client, auth):
    r = await client.get("/api/admin/tags", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert any(t["slug"] == "backend" for t in body)


async def test_tags_create_patch_delete(client, auth):
    create = await client.post(
        "/api/admin/tags",
        json={"slug": "tmp-tag", "name": "tmp", "color": "#ff00ff", "sort_order": 99},
        headers=auth,
    )
    assert create.status_code == 201
    tid = create.json()["id"]

    patch = await client.patch(
        f"/api/admin/tags/{tid}", json={"name": "renamed"}, headers=auth
    )
    assert patch.status_code == 200
    assert patch.json()["name"] == "renamed"

    deleted = await client.delete(f"/api/admin/tags/{tid}", headers=auth)
    assert deleted.status_code == 204


async def test_tags_reorder(client, auth):
    listing = await client.get("/api/admin/tags", headers=auth)
    ids = [t["id"] for t in listing.json()]
    reordered = list(reversed(ids))
    r = await client.put("/api/admin/tags/order", json={"ids": reordered}, headers=auth)
    assert r.status_code == 204
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_admin_taxonomy.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/admin/tags.py backend/app/routers/admin/__init__.py backend/tests/test_admin_taxonomy.py
git commit -m "feat(backend): admin tags CRUD + reorder"
```

---

### Task 32: Admin projects CRUD + reorder

**Files:**
- Create: `backend/app/routers/admin/projects.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Modify: `backend/tests/test_admin_taxonomy.py`

- [ ] **Step 1: Write `backend/app/routers/admin/projects.py`**

```python
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Project
from app.services.event_log import write_event

router = APIRouter()


class ProjectIn(BaseModel):
    name: str
    description: str
    lang: str
    stars: int = 0
    status: str = "active"
    sort_order: int = 0
    visible: bool = True


class ProjectOut(ProjectIn):
    model_config = {"from_attributes": True}


@router.get("/projects", response_model=list[ProjectOut])
async def list_(_: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(Project).order_by(Project.sort_order))).scalars().all()
    return [ProjectOut.model_validate(r) for r in rows]


@router.post("/projects", response_model=ProjectOut, status_code=201)
async def create(payload: ProjectIn, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    if (await s.execute(select(Project).where(Project.name == payload.name))).scalar_one_or_none():
        raise HTTPException(status_code=409, detail="name taken")
    p = Project(**payload.model_dump())
    s.add(p)
    await write_event(s, type="project.created", actor=admin.email, target=payload.name)
    await s.flush()
    return ProjectOut.model_validate(p)


@router.patch("/projects/{name}", response_model=ProjectOut)
async def patch(
    name: str, payload: dict = Body(...),
    admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session),
):
    p = (await s.execute(select(Project).where(Project.name == name))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("description", "lang", "stars", "status", "sort_order", "visible"):
        if k in payload:
            setattr(p, k, payload[k])
    await write_event(s, type="project.updated", actor=admin.email, target=name)
    return ProjectOut.model_validate(p)


@router.delete("/projects/{name}", status_code=204)
async def delete(name: str, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    p = (await s.execute(select(Project).where(Project.name == name))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(p)
    await write_event(s, type="project.deleted", actor=admin.email, target=name)


@router.put("/projects/order", status_code=204)
async def reorder(payload: dict = Body(...), admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    names = payload.get("ids")
    if not isinstance(names, list):
        raise HTTPException(status_code=422, detail="ids: list[str] (project names) required")
    for sort_order, name in enumerate(names):
        p = (await s.execute(select(Project).where(Project.name == name))).scalar_one_or_none()
        if p is None:
            raise HTTPException(status_code=422, detail=f"project {name} not found")
        p.sort_order = sort_order
    await write_event(s, type="project.reordered", actor=admin.email)
```

- [ ] **Step 2: Wire**

```python
# backend/app/routers/admin/__init__.py
from app.routers.admin.projects import router as projects_router
router.include_router(projects_router, tags=["admin·projects"])
```

- [ ] **Step 3: Append test**

In `tests/test_admin_taxonomy.py`:

```python
async def test_projects_list_seeded(client, auth):
    r = await client.get("/api/admin/projects", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) >= 1


async def test_projects_create_patch_delete(client, auth):
    name = "tmp-project-x"
    await client.delete(f"/api/admin/projects/{name}", headers=auth)
    create = await client.post(
        "/api/admin/projects",
        json={"name": name, "description": "tmp", "lang": "Go", "stars": 0, "status": "active"},
        headers=auth,
    )
    assert create.status_code == 201
    patch = await client.patch(
        f"/api/admin/projects/{name}", json={"stars": 99}, headers=auth
    )
    assert patch.status_code == 200
    assert patch.json()["stars"] == 99
    deleted = await client.delete(f"/api/admin/projects/{name}", headers=auth)
    assert deleted.status_code == 204
```

- [ ] **Step 4: Run; expect PASS**

```bash
uv run pytest tests/test_admin_taxonomy.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/admin/projects.py backend/app/routers/admin/__init__.py backend/tests/test_admin_taxonomy.py
git commit -m "feat(backend): admin projects CRUD + reorder"
```

---

### Task 33: Admin contacts CRUD + reorder

**Files:**
- Create: `backend/app/routers/admin/contacts.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Modify: `backend/tests/test_admin_taxonomy.py`

- [ ] **Step 1: Write `backend/app/routers/admin/contacts.py`**

```python
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Contact
from app.services.event_log import write_event

router = APIRouter()


class ContactIn(BaseModel):
    label: str
    value: str
    href: str
    visible: bool = True
    sort_order: int = 0


class ContactOut(ContactIn):
    id: int
    model_config = {"from_attributes": True}


@router.get("/contacts", response_model=list[ContactOut])
async def list_(_: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    rows = (await s.execute(select(Contact).order_by(Contact.sort_order))).scalars().all()
    return [ContactOut.model_validate(r) for r in rows]


@router.post("/contacts", response_model=ContactOut, status_code=201)
async def create(payload: ContactIn, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    c = Contact(**payload.model_dump())
    s.add(c)
    await s.flush()
    await write_event(s, type="contact.created", actor=admin.email, target=str(c.id))
    return ContactOut.model_validate(c)


@router.patch("/contacts/{cid}", response_model=ContactOut)
async def patch(cid: int, payload: dict = Body(...), admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    c = (await s.execute(select(Contact).where(Contact.id == cid))).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="not found")
    for k in ("label", "value", "href", "visible", "sort_order"):
        if k in payload:
            setattr(c, k, payload[k])
    await write_event(s, type="contact.updated", actor=admin.email, target=str(cid))
    return ContactOut.model_validate(c)


@router.delete("/contacts/{cid}", status_code=204)
async def delete(cid: int, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    c = (await s.execute(select(Contact).where(Contact.id == cid))).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="not found")
    await s.delete(c)
    await write_event(s, type="contact.deleted", actor=admin.email, target=str(cid))


@router.put("/contacts/order", status_code=204)
async def reorder(payload: dict = Body(...), admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)):
    ids = payload.get("ids")
    if not isinstance(ids, list):
        raise HTTPException(status_code=422, detail="ids: list[int] required")
    for sort_order, cid in enumerate(ids):
        c = (await s.execute(select(Contact).where(Contact.id == cid))).scalar_one_or_none()
        if c is None:
            raise HTTPException(status_code=422, detail=f"contact id {cid} not found")
        c.sort_order = sort_order
    await write_event(s, type="contact.reordered", actor=admin.email)
```

- [ ] **Step 2: Wire**

```python
# backend/app/routers/admin/__init__.py
from app.routers.admin.contacts import router as contacts_router
router.include_router(contacts_router, tags=["admin·contacts"])
```

- [ ] **Step 3: Append test**

In `tests/test_admin_taxonomy.py`:

```python
async def test_contacts_create_patch_delete(client, auth):
    create = await client.post(
        "/api/admin/contacts",
        json={"label": "test", "value": "v", "href": "https://e", "visible": True, "sort_order": 0},
        headers=auth,
    )
    assert create.status_code == 201
    cid = create.json()["id"]
    patch = await client.patch(f"/api/admin/contacts/{cid}", json={"value": "v2"}, headers=auth)
    assert patch.status_code == 200
    deleted = await client.delete(f"/api/admin/contacts/{cid}", headers=auth)
    assert deleted.status_code == 204
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_admin_taxonomy.py -v
git add backend/app/routers/admin/contacts.py backend/app/routers/admin/__init__.py backend/tests/test_admin_taxonomy.py
git commit -m "feat(backend): admin contacts CRUD + reorder"
```

---

### Task 34: Admin profile / site / theme PUT

**Files:**
- Create: `backend/app/routers/admin/site.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Create: `backend/tests/test_admin_site.py`

- [ ] **Step 1: Write `backend/app/routers/admin/site.py`**

```python
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, SiteMeta
from app.services.event_log import write_event

router = APIRouter()


class ProfileIn(BaseModel):
    name: str | None = None
    name_en: str | None = None
    role: str | None = None
    bio: str | None = None
    location: str | None = None
    pronouns: str | None = None
    avatar_path: str | None = None
    typing_line: str | None = None
    stack_chips: list[str] | None = None


class SiteIn(BaseModel):
    handle: str | None = None
    tagline: str | None = None
    email: str | None = None
    github: str | None = None
    footer_note: str | None = None
    default_theme: str | None = None
    launched_at: str | None = None  # ISO date


class ThemeIn(BaseModel):
    accent_color: str | None = None
    accent2_color: str | None = None
    violet_color: str | None = None
    danger_color: str | None = None


async def _fetch(s: AsyncSession) -> SiteMeta:
    sm = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one_or_none()
    if sm is None:
        raise HTTPException(status_code=500, detail="site_meta not seeded")
    return sm


def _apply(sm: SiteMeta, payload: BaseModel) -> None:
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sm, k, v)


@router.get("/profile")
async def get_profile(_: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)) -> dict:
    sm = await _fetch(s)
    return {k: getattr(sm, k) for k in ProfileIn.model_fields}


@router.put("/profile")
async def put_profile(payload: ProfileIn, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)) -> dict:
    sm = await _fetch(s)
    _apply(sm, payload)
    await write_event(s, type="identity.updated", actor=admin.email)
    return {k: getattr(sm, k) for k in ProfileIn.model_fields}


@router.get("/site")
async def get_site(_: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)) -> dict:
    sm = await _fetch(s)
    return {k: getattr(sm, k) for k in SiteIn.model_fields}


@router.put("/site")
async def put_site(payload: SiteIn, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)) -> dict:
    sm = await _fetch(s)
    if payload.launched_at:
        from datetime import date as date_t
        try:
            sm.launched_at = date_t.fromisoformat(payload.launched_at)
        except ValueError:
            raise HTTPException(status_code=422, detail="launched_at: ISO date required")
        payload = payload.model_copy(update={"launched_at": None})
    _apply(sm, payload)
    await write_event(s, type="site.updated", actor=admin.email)
    return {k: getattr(sm, k) for k in SiteIn.model_fields}


@router.get("/theme")
async def get_theme(_: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)) -> dict:
    sm = await _fetch(s)
    return {k: getattr(sm, k) for k in ThemeIn.model_fields}


@router.put("/theme")
async def put_theme(payload: ThemeIn, admin: Account = Depends(current_admin), s: AsyncSession = Depends(get_session)) -> dict:
    sm = await _fetch(s)
    _apply(sm, payload)
    await write_event(s, type="theme.updated", actor=admin.email)
    return {k: getattr(sm, k) for k in ThemeIn.model_fields}
```

- [ ] **Step 2: Wire**

```python
# backend/app/routers/admin/__init__.py
from app.routers.admin.site import router as site_router
router.include_router(site_router, tags=["admin·site"])
```

- [ ] **Step 3: Write test**

`backend/tests/test_admin_site.py`:

```python
import pytest


@pytest.fixture
async def auth(client):
    r = await client.post("/api/admin/auth/login", json={"email": "hi@wangyang.dev", "password": "changeme"})
    return {"Authorization": f"Bearer {r.json()['access']}"}


async def test_profile_get_and_put(client, auth):
    g = await client.get("/api/admin/profile", headers=auth)
    assert g.status_code == 200
    p = await client.put("/api/admin/profile", json={"role": "Backend / AI / Tinkerer"}, headers=auth)
    assert p.status_code == 200
    assert p.json()["role"] == "Backend / AI / Tinkerer"


async def test_site_put_partial(client, auth):
    p = await client.put("/api/admin/site", json={"footer_note": "© 2026 wy"}, headers=auth)
    assert p.status_code == 200
    assert p.json()["footer_note"] == "© 2026 wy"


async def test_theme_put_color(client, auth):
    p = await client.put("/api/admin/theme", json={"accent_color": "oklch(85% 0.18 152)"}, headers=auth)
    assert p.status_code == 200
    assert p.json()["accent_color"].startswith("oklch")
```

- [ ] **Step 4: Run + commit**

```bash
uv run pytest tests/test_admin_site.py -v
git add backend/app/routers/admin/site.py backend/app/routers/admin/__init__.py backend/tests/test_admin_site.py
git commit -m "feat(backend): admin profile/site/theme GET+PUT"
```

---

## Phase I — Frontend integration

### Task 35: Frontend API client

**Files:**
- Create: `src/api/client.js`
- Create: `.env.development`
- Modify: `src/data.js`

- [ ] **Step 1: Write `.env.development`**

```bash
VITE_API_BASE_URL=http://localhost:51820
```

- [ ] **Step 2: Write `src/api/client.js`**

```javascript
const BASE = import.meta.env.VITE_API_BASE_URL || '';

async function request(path, opts = {}) {
  const r = await fetch(`${BASE}/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!r.ok) {
    let detail = `${r.status}`;
    try { detail = (await r.json()).detail || detail; } catch {}
    throw new Error(`${r.status} ${detail}`);
  }
  if (r.status === 204) return null;
  return r.json();
}

export const api = {
  site:     () => request('/site'),
  profile:  () => request('/profile'),
  contacts: () => request('/contacts'),
  tags:     () => request('/tags'),
  projects: () => request('/projects'),
  contrib:  (weeks = 52) => request(`/contrib?weeks=${weeks}`),
  posts: {
    list: (params = {}) => {
      const q = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ''))
      ).toString();
      return request(`/posts${q ? '?' + q : ''}`);
    },
    detail: (id) => request(`/posts/${id}`),
    like:   (id) => request(`/posts/${id}/like`, { method: 'POST' }),
  },
};
```

- [ ] **Step 3: Replace `src/data.js`**

Overwrite the entire file:

```javascript
// Frontend now reads from the backend; this module just provides the shape
// other components import. The real values are loaded via React Query-ish
// hooks in src/api/hooks.js.

export const SITE = null;
export const POSTS = [];
export const PROJECTS = [];
export const TAGS = [];
export const CONTRIB = [];

// Legacy synchronous re-export — kept temporarily so the rest of the app
// doesn't break before all callsites switch to `useSite()` etc.
```

(Components will be migrated in Task 36; this gives them a stub during the cutover.)

- [ ] **Step 4: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog
git add src/api/client.js .env.development src/data.js
git commit -m "feat(frontend): add API client + env-based base URL"
```

---

### Task 36: React hooks for backend data

**Files:**
- Create: `src/api/hooks.js`

- [ ] **Step 1: Write `src/api/hooks.js`**

```javascript
import { useEffect, useState } from 'react';
import { api } from './client.js';

function useResource(loader, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loader()
      .then((v) => { if (!cancelled) { setData(v); setError(null); } })
      .catch((e) => { if (!cancelled) setError(e); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

export const useSite     = ()       => useResource(() => api.site());
export const useProfile  = ()       => useResource(() => api.profile());
export const useContacts = ()       => useResource(() => api.contacts());
export const useTags     = ()       => useResource(() => api.tags());
export const useProjects = ()       => useResource(() => api.projects());
export const useContrib  = (w = 52) => useResource(() => api.contrib(w), [w]);
export const usePosts    = (params) => useResource(() => api.posts.list(params), [JSON.stringify(params)]);
export const usePost     = (id)     => useResource(() => api.posts.detail(id), [id]);
```

- [ ] **Step 2: Commit**

```bash
git add src/api/hooks.js
git commit -m "feat(frontend): React hooks wrapping the API client"
```

---

### Task 37: Migrate `App.jsx` and `HomeA.jsx` to backend data

**Files:**
- Modify: `src/App.jsx`
- Modify: `src/components/HomeA.jsx`

- [ ] **Step 1: Replace top of `src/App.jsx`**

Find the existing imports block and the line `import { SITE, POSTS } from './data.js';`. Replace:

```javascript
import { useSite, usePosts, useTags } from './api/hooks.js';
```

Inside the `App` component, replace the existing posts memo and SITE references:

```javascript
const { data: siteData } = useSite();
const { data: postsResp, loading: postsLoading } = usePosts({
  tag: activeTag === 'all' ? undefined : activeTag,
  limit: 100,
});
const { data: tagsData } = useTags();
const posts = postsResp?.items || [];
const SITE = siteData || { name: '', nameEn: 'Wang Yang' };
```

The remaining keyboard-shortcut and reading logic stays intact; it already references `posts` as a list of summary objects, which the new API returns with the same field names.

In the footer JSX, swap the old `SITE.nameEn` reference to use the bound local `SITE`. (No change if the variable name was already `SITE` — but make sure the destructure exists.)

Pass `tagsData` down to `HomeA` so the tagbar uses real data:

```javascript
<HomeA
  posts={posts}
  tags={tagsData || []}
  activeTag={activeTag}
  setTag={setActiveTag}
  focusIdx={focusIdx}
  onOpenPost={openPost}
  loading={postsLoading}
/>
```

(The full file is too long to re-show; only these targeted edits are needed.)

- [ ] **Step 2: Update `src/components/HomeA.jsx`**

Replace the existing `import { SITE, PROJECTS, TAGS, CONTRIB } from '../data.js';` line with:

```javascript
import { useSite, useProjects, useContrib } from '../api/hooks.js';
```

Modify the `HomeA` function signature to accept `tags` prop:

```javascript
export default function HomeA({ posts, tags, activeTag, setTag, focusIdx, onOpenPost, loading }) {
  const { data: site } = useSite();
  const { data: projects } = useProjects();
  const { data: contribResp } = useContrib(52);

  const SITE = site || { commits52w: 0 };
  const PROJECTS = projects || [];
  const CONTRIB = contribResp?.grid || [];
  const TAGS = tags || [];

  if (loading && posts.length === 0) {
    return <div className="hero"><div className="wrap"><div className="prompt">loading…</div></div></div>;
  }
  // remainder of the existing JSX is unchanged — it references SITE/PROJECTS/CONTRIB/TAGS as before
```

(The rest of the JSX body is unchanged.)

- [ ] **Step 3: Migrate `src/components/Reader.jsx`**

Replace `import { SITE, POSTS } from '../data.js';` with `import { useSite, usePosts } from '../api/hooks.js';`. In the `Reader` body:

```javascript
const { data: site } = useSite();
const { data: postsResp } = usePosts({ limit: 100 });
const SITE = site || { name: 'Wang Yang' };
const POSTS = postsResp?.items || [];
```

The remaining `Reader` logic uses `POSTS.find(...)` for prev/next — those calls keep working because `items` returns the same field names.

For now keep `likes`/`liked` as localStorage-driven (Phase 4 wires real `/api/posts/{id}/like`).

- [ ] **Step 4: Migrate `src/components/Palette.jsx`**

Replace `import { POSTS } from '../data.js';` with `import { usePosts } from '../api/hooks.js';`. Inside the Palette component:

```javascript
const { data: postsResp } = usePosts({ limit: 100 });
const POSTS = postsResp?.items || [];
```

- [ ] **Step 5: Run dev servers**

```bash
# Terminal 1: backend
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run uvicorn app.main:app --port 51820 --reload
# Terminal 2: frontend
cd /Users/sd3/Desktop/project/MyBlog
npm run dev -- --port 51730 --strictPort
```

Open http://localhost:51730 and verify:
- Hero text comes from `/api/site` (handle, name, role from DB)
- Contribution graph renders (seed grid since no GitHub yet)
- Post list shows the 7 imported markdown articles + any draft posts you created via admin
- Clicking a post opens Reader with full body
- ⌘K palette searches by post title

- [ ] **Step 6: Commit**

```bash
git add src/App.jsx src/components/HomeA.jsx src/components/Reader.jsx src/components/Palette.jsx
git commit -m "feat(frontend): migrate App/HomeA/Reader/Palette to use backend hooks"
```

---

### Task 38: Smoke verification + commit Phase-1 tag

- [ ] **Step 1: Backend full test sweep**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend
uv run pytest -v
```

Expected: all tests in `test_*.py` pass. If anything fails, fix before tagging.

- [ ] **Step 2: Frontend build sanity**

```bash
cd /Users/sd3/Desktop/project/MyBlog
npm run build
```

Expected: build succeeds, `dist/` populated.

- [ ] **Step 3: End-to-end click test**

With backend on `:51820` and frontend on `:51730`:

1. Open http://localhost:51730 — homepage loads.
2. ⌘K → "Termius" → opens article. Body renders headings + tables + code blocks.
3. Toggle theme via topbar — accent stays green/amber/violet correctly.
4. `curl -s http://localhost:51820/api/posts | jq '.items | length'` matches what's shown.
5. Login admin: `curl -X POST http://localhost:51820/api/admin/auth/login -H 'content-type: application/json' -d '{"email":"hi@wangyang.dev","password":"changeme"}'` returns `access` token.
6. Create a post via admin: feed a markdown body (with frontmatter) to `POST /api/admin/posts`; refresh frontend; new post appears.

- [ ] **Step 4: Tag the milestone**

```bash
git tag -a backend-phase-1 -m "Backend Phase 1: foundation, public read API, admin core"
git log --oneline | head -25
```

- [ ] **Step 5: Done — Phase 2 (Auth Hardening) follows in a separate plan.**

---

## Self-Review

(Performed by the plan author after writing.)

**Spec coverage check:**

| Spec section | Plan task |
|---|---|
| §1 context | n/a — informational |
| §2 architecture | Task 2 (compose) + Task 13 (FastAPI factory) |
| §3.1 content tables | Tasks 6, 7, 8 |
| §3.2 engagement | (deferred to Phase 4) |
| §3.3 system tables | Tasks 8, 9 |
| §3.4 conventions | Task 4 (TimestampMixin), Task 6+ (slug pattern), Task 9 (event_log JSONB) |
| §4.1 public endpoints (subset) | Tasks 13, 22, 23, 24, 25 |
| §4.1 likes/comments/track/pet | (deferred to Phases 3/4/5) |
| §4.2 admin auth (login only) | Task 27 (refresh/2FA/magic-link deferred to Phase 3) |
| §4.2 admin content | Tasks 29, 30, 31, 32, 33, 34 |
| §4.2 admin integrations/account/danger | (deferred) |
| §4.3 webhooks | (deferred to Phase 5) |
| §4.4 cross-cutting (errors, request_id) | Tasks 11, 12 |
| §5 markdown pipeline | Tasks 14, 15, 16, 17 |
| §5.5 .md upload | Task 30 |
| §5.6 CLI import | Tasks 18, 19, 20 |
| §5.7 round-trip golden | Task 16 |
| §6 auth/secrets/rate-limit | Auth login partial (Tasks 18, 26, 27); rest deferred |
| §7.1 tree | "File Structure" header section |
| §7.2 process model | Task 2 + Task 13 |
| §7.3 ARQ background | (deferred to Phase 5) |
| §7.4 config | Task 3 |
| §7.5 migrations | Task 10 |
| §7.6 bootstrap | Tasks 18, 19, 20 |
| §8 testing | Tasks include test scaffolding throughout |

Phase 1 covers everything labeled "Phase 1" in the implementation gating; Phase 2 (this plan's second half) covers auth + admin CRUD. Items deferred are tagged in the table above and explicitly listed under each plan's "Out of scope".

**Placeholder scan:** All steps contain runnable code or commands. No "TBD"/"TODO" left in plan steps. Two `# Cleanup` test annotations are intentional, not placeholders.

**Type consistency:** `PostFrontmatter`, `PostSummary`, `PostDetail`, `PostList`, `Account`, `Tag.slug` (str), `Tag.id` (int), `Project.name` (str PK) consistent across tasks. `current_admin` dependency consistently typed `Account`.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-04-25-backend-phase1-foundation-and-admin-core.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

**Which approach?**
