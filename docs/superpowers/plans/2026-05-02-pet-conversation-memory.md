# Pet Conversation Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the desktop pet a per-visitor conversation memory: 10-turn rolling Redis context (2h sliding TTL) injected into the LLM's messages array, plus full permanent archive in a new `pet_message` Postgres table, plus an admin tab to browse, drill into, and delete conversations.

**Architecture:** New `pet_context.py` service for Redis hot path; new `pet_message` model + alembic migration for cold archive. Gateway + adapters upgrade from `user: str` to `messages: list[dict]`. The summon endpoint loads prior turns from Redis, builds the messages array, streams the reply, then fire-and-forgets a background task to append to Redis and archive to Postgres.

**Tech Stack:** FastAPI + Pydantic v2 · async SQLAlchemy 2.0 · alembic · Redis 7 (fakeredis in tests) · pytest-asyncio · React 18 + Vite + React Router · vitest + jsdom

**Reference spec:** `docs/superpowers/specs/2026-05-02-pet-conversation-memory-design.md`

---

## File Structure

**Create:**
- `backend/app/models/pet_message.py` — SQLAlchemy `PetMessage` model
- `backend/alembic/versions/0012_add_pet_message.py` — alembic migration
- `backend/app/services/pet_context.py` — `load`, `append`, `clear` over Redis list
- `backend/tests/test_pet_message_model.py` — model insert/roundtrip tests
- `backend/tests/test_pet_context.py` — Redis service unit tests
- `backend/tests/test_pet_prompt_messages.py` — `build_messages` unit tests
- `backend/tests/test_pet_summon_stream_history.py` — integration: history flows end-to-end
- `backend/tests/test_admin_pet_conversations.py` — admin endpoint tests
- `src/admin/pet/PetConversations.jsx` — list grouped by visitor_hash
- `src/admin/pet/PetConversationDetail.jsx` — message timeline + debug folds
- `src/admin/pet/PetConversations.test.jsx`
- `src/admin/pet/PetConversationDetail.test.jsx`

**Modify:**
- `backend/app/models/__init__.py` — export `PetMessage`
- `backend/app/schemas/pet.py` — add `context_window_turns`, `context_ttl_seconds`
- `backend/app/services/pet_prompt.py` — add `build_messages`
- `backend/app/services/pet_adapters/openai_compat.py` — `chat_stream` accepts `messages`
- `backend/app/services/pet_adapters/anthropic.py` — `chat_stream` accepts `messages`
- `backend/app/services/pet_gateway.py` — `summon_stream` accepts `messages`; legacy `summon` wraps
- `backend/app/routers/public/pet.py` — wire context load + build_messages + post-stream archive
- `backend/app/routers/admin/pet.py` — three new endpoints
- `src/api/pet.js` — `listConversations`, `getConversation`, `deleteConversation`
- `src/admin/Pet.jsx` — add `conversations` tab + route

---

## Task 1: PetMessage model + alembic migration

**Files:**
- Create: `backend/app/models/pet_message.py`
- Create: `backend/alembic/versions/0012_add_pet_message.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_pet_message_model.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pet_message_model.py
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models import PetMessage


async def test_insert_pet_message_basic_roundtrip():
    async with AsyncSession(engine) as s:
        m = PetMessage(
            visitor_hash="abc123def456",
            species="cat",
            mode="greet",
            post_id=None,
            title=None,
            tag_slug=None,
            summary=None,
            selection=None,
            system_prompt="you are cat",
            prior_turns=[],
            reply="meow",
            source="zhipu",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        assert m.id is not None
        assert isinstance(m.created_at, datetime)
        # Cleanup
        await s.delete(m)
        await s.commit()


async def test_prior_turns_jsonb_roundtrip():
    async with AsyncSession(engine) as s:
        prior = [
            {"role": "user", "content": "hi", "mode": "greet", "post_id": None},
            {"role": "assistant", "content": "hello there", "mode": "greet", "post_id": None},
        ]
        m = PetMessage(
            visitor_hash="abc",
            species="cat",
            mode="summary_react",
            post_id="hello",
            title="Hello",
            tag_slug="devtools",
            summary="An article",
            selection=None,
            system_prompt="...",
            prior_turns=prior,
            reply="hi back",
            source="anthropic",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        assert m.prior_turns == prior
        await s.delete(m)
        await s.commit()


async def test_selection_can_be_null():
    async with AsyncSession(engine) as s:
        m = PetMessage(
            visitor_hash="x",
            species="cat",
            mode="greet",
            system_prompt="x",
            prior_turns=[],
            reply="x",
            source="fallback",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        assert m.selection is None
        await s.delete(m)
        await s.commit()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_message_model.py -v
```
Expected: ImportError — `PetMessage` not in `app.models`.

- [ ] **Step 3: Create the model file**

Create `backend/app/models/pet_message.py`:

```python
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PetMessage(Base):
    """Permanent archive of every pet summon turn.

    Companion to the Redis short-term context (pet_context.py): Redis
    holds the live 10-turn window for LLM injection; this table holds
    the durable history admins can browse, search, and analyze.
    """

    __tablename__ = "pet_message"
    __table_args__ = (
        Index("ix_pet_message_visitor_hash_created", "visitor_hash", "created_at"),
        Index("ix_pet_message_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    visitor_hash: Mapped[str] = mapped_column(String(16), nullable=False)
    species: Mapped[str] = mapped_column(String(32), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    post_id: Mapped[str | None] = mapped_column(String(80))
    title: Mapped[str | None] = mapped_column(String(200))
    tag_slug: Mapped[str | None] = mapped_column(String(40))
    summary: Mapped[str | None] = mapped_column(Text)
    selection: Mapped[str | None] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    prior_turns: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    reply: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
```

- [ ] **Step 4: Add to models __init__**

Edit `backend/app/models/__init__.py`. Insert the import alphabetically (after `now_entry`, before `post`) and add `"PetMessage"` to `__all__` (place between `"NowEntry"` and `"Post"`):

```python
from app.models.pet_message import PetMessage
```

The `__all__` block becomes:
```python
__all__ = [
    "Base", "TimestampMixin",
    "Account", "ApiToken", "Comment", "Contact", "ContribDay", "EventLog",
    "EventLogArchive",
    "ExportJob",
    "HitDaily", "HitEvent",
    "Integration", "LikeEvent", "MagicLink", "Media", "NowEntry",
    "PetMessage",
    "Post", "Project",
    "SiteMeta", "Tag", "TfaRecoveryCode",
]
```

- [ ] **Step 5: Create the alembic migration**

Create `backend/alembic/versions/0012_add_pet_message.py`:

```python
"""add pet_message table

Revision ID: 0012_add_pet_message
Revises: 0011_pet_add_deepseek
Create Date: 2026-05-02

Companion to Redis pet:ctx:* short-term context: the durable archive
of every pet summon turn for admin browsing.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_add_pet_message"
down_revision: str | None = "0011_pet_add_deepseek"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pet_message",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("visitor_hash", sa.String(16), nullable=False),
        sa.Column("species", sa.String(32), nullable=False),
        sa.Column("mode", sa.String(32), nullable=False),
        sa.Column("post_id", sa.String(80), nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("tag_slug", sa.String(40), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("selection", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "prior_turns",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("reply", sa.Text(), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_pet_message_visitor_hash_created",
        "pet_message",
        ["visitor_hash", "created_at"],
    )
    op.create_index("ix_pet_message_created_at", "pet_message", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_pet_message_created_at", table_name="pet_message")
    op.drop_index("ix_pet_message_visitor_hash_created", table_name="pet_message")
    op.drop_table("pet_message")
```

- [ ] **Step 6: Apply migration to test DB**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run alembic upgrade head
```
Expected: `INFO ... Running upgrade 0011_pet_add_deepseek -> 0012_add_pet_message, add pet_message table`

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_message_model.py -v
```
Expected: 3 passed.

- [ ] **Step 8: Apply migration to dev DB too**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env && set +a && uv run alembic upgrade head
```
Expected: same upgrade message. (This is the running app's DB; without it the new endpoints will 500 in the browser.)

- [ ] **Step 9: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/models/pet_message.py backend/app/models/__init__.py backend/alembic/versions/0012_add_pet_message.py backend/tests/test_pet_message_model.py
git commit -m "feat(pet): pet_message model + 0012 migration"
```

---

## Task 2: pet_context service (Redis hot ctx)

**Files:**
- Create: `backend/app/services/pet_context.py`
- Test: `backend/tests/test_pet_context.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pet_context.py
import pytest
import fakeredis.aioredis

from app.services.pet_context import (
    DEFAULT_MAX_TURNS,
    DEFAULT_TTL_SEC,
    KEY_PREFIX,
    append,
    clear,
    load,
)


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


async def test_load_returns_empty_when_no_history(redis):
    assert await load(redis, "v1") == []


async def test_append_then_load_returns_chronological_pair(redis):
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "hi"},
        assistant_turn={"role": "assistant", "content": "hello"},
    )
    out = await load(redis, "v1")
    assert out == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


async def test_multiple_appends_keep_chronological_order(redis):
    for i in range(3):
        await append(
            redis, "v1",
            user_turn={"role": "user", "content": f"u{i}"},
            assistant_turn={"role": "assistant", "content": f"a{i}"},
        )
    out = await load(redis, "v1")
    contents = [t["content"] for t in out]
    assert contents == ["u0", "a0", "u1", "a1", "u2", "a2"]


async def test_append_caps_at_2x_max_turns(redis):
    for i in range(15):
        await append(
            redis, "v1",
            user_turn={"role": "user", "content": f"u{i}"},
            assistant_turn={"role": "assistant", "content": f"a{i}"},
            max_turns=5,
        )
    out = await load(redis, "v1", max_turns=5)
    assert len(out) == 10  # 5 pairs
    contents = [t["content"] for t in out]
    # Most recent 5 pairs, chronological
    assert contents == ["u10", "a10", "u11", "a11", "u12", "a12", "u13", "a13", "u14", "a14"]


async def test_load_with_smaller_max_turns_truncates(redis):
    for i in range(5):
        await append(
            redis, "v1",
            user_turn={"role": "user", "content": f"u{i}"},
            assistant_turn={"role": "assistant", "content": f"a{i}"},
        )
    out = await load(redis, "v1", max_turns=2)
    assert len(out) == 4
    contents = [t["content"] for t in out]
    assert contents == ["u3", "a3", "u4", "a4"]


async def test_append_resets_ttl_each_call(redis):
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "a"},
        assistant_turn={"role": "assistant", "content": "b"},
        ttl_sec=100,
    )
    ttl1 = await redis.ttl(f"{KEY_PREFIX}v1")
    assert 90 <= ttl1 <= 100
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "c"},
        assistant_turn={"role": "assistant", "content": "d"},
        ttl_sec=300,
    )
    ttl2 = await redis.ttl(f"{KEY_PREFIX}v1")
    assert 290 <= ttl2 <= 300


async def test_clear_deletes_key(redis):
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "a"},
        assistant_turn={"role": "assistant", "content": "b"},
    )
    await clear(redis, "v1")
    assert await load(redis, "v1") == []


async def test_default_constants():
    assert DEFAULT_MAX_TURNS == 10
    assert DEFAULT_TTL_SEC == 7200
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_context.py -v
```
Expected: ImportError — `pet_context` module not found.

- [ ] **Step 3: Implement `pet_context.py`**

Create `backend/app/services/pet_context.py`:

```python
"""Per-visitor short-term conversation context for the pet.

Keyed by visitor_hash (ip_hash[:16]); stored as a Redis list with a
2h sliding TTL and capped at 2*max_turns members. Newest first
(LPUSH); load() reverses to chronological order.

Failures during load/append are NOT propagated — Redis is a cache,
not a source of truth. Callers fall back to "fresh" state when load
fails, and skip remembering the latest turn when append fails.
The companion archive in pet_message (Postgres) is the durable record.
"""
from __future__ import annotations

import json

from redis.asyncio import Redis

KEY_PREFIX = "pet:ctx:"
DEFAULT_MAX_TURNS = 10
DEFAULT_TTL_SEC = 7200


def _key(visitor_hash: str) -> str:
    return f"{KEY_PREFIX}{visitor_hash}"


async def load(
    redis: Redis,
    visitor_hash: str,
    *,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> list[dict]:
    """Return prior turns oldest-first, at most 2*max_turns members."""
    cap = max_turns * 2
    raw = await redis.lrange(_key(visitor_hash), 0, cap - 1)
    out: list[dict] = []
    for s in reversed(list(raw)):
        try:
            out.append(json.loads(s))
        except (TypeError, ValueError):
            continue
    return out


async def append(
    redis: Redis,
    visitor_hash: str,
    *,
    user_turn: dict,
    assistant_turn: dict,
    max_turns: int = DEFAULT_MAX_TURNS,
    ttl_sec: int = DEFAULT_TTL_SEC,
) -> None:
    """Atomically prepend user+assistant, trim, and reset TTL."""
    key = _key(visitor_hash)
    cap = max_turns * 2 - 1
    # The list is newest-first (LPUSH); push assistant first then user
    # so user ends up at index 0 — chronologically first when load
    # reverses the list.
    pipe = redis.pipeline()
    pipe.lpush(key, json.dumps(assistant_turn, ensure_ascii=False))
    pipe.lpush(key, json.dumps(user_turn, ensure_ascii=False))
    pipe.ltrim(key, 0, cap)
    pipe.expire(key, ttl_sec)
    await pipe.execute()


async def clear(redis: Redis, visitor_hash: str) -> None:
    await redis.delete(_key(visitor_hash))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_context.py -v
```
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/services/pet_context.py backend/tests/test_pet_context.py
git commit -m "feat(pet): pet_context Redis service (load/append/clear)"
```

---

## Task 3: PetConfig schema additions

**Files:**
- Modify: `backend/app/schemas/pet.py`
- Test: extend `backend/tests/test_pet_schema.py`

- [ ] **Step 1: Append the failing test**

Append to `backend/tests/test_pet_schema.py`:

```python
def test_context_window_turns_default_and_bounds():
    c = PetConfig()
    assert c.context_window_turns == 10
    with pytest.raises(ValidationError):
        PetConfig(context_window_turns=0)
    with pytest.raises(ValidationError):
        PetConfig(context_window_turns=51)


def test_context_ttl_seconds_default_and_bounds():
    c = PetConfig()
    assert c.context_ttl_seconds == 7200
    with pytest.raises(ValidationError):
        PetConfig(context_ttl_seconds=59)
    with pytest.raises(ValidationError):
        PetConfig(context_ttl_seconds=86401)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_schema.py -v
```
Expected: AttributeError — `context_window_turns` not on `PetConfig`.

- [ ] **Step 3: Add the fields**

In `backend/app/schemas/pet.py`, locate the `PetConfig` class. Just after the `hard_ceiling_per_day` field (the last `# NEW` field added previously), insert:

```python
    context_window_turns: int = Field(default=10, ge=1, le=50)
    context_ttl_seconds: int = Field(default=7200, ge=60, le=86400)
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_schema.py tests/test_pet_defaults.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/schemas/pet.py backend/tests/test_pet_schema.py
git commit -m "feat(pet): context_window_turns + context_ttl_seconds in PetConfig"
```

---

## Task 4: pet_prompt.build_messages

**Files:**
- Modify: `backend/app/services/pet_prompt.py`
- Test: `backend/tests/test_pet_prompt_messages.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pet_prompt_messages.py`:

```python
from app.schemas.pet import PetConfig
from app.services.pet_prompt import build_messages


def test_build_messages_with_empty_prior_yields_one_user_turn():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="greet",
        title=None, tag=None, summary=None, selection=None,
        prior=[],
    )
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "tapped on you" in msgs[0]["content"]


def test_build_messages_summary_react_scene_tag():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="summary_react",
        title="Hello", tag="devtools", summary="A summary.", selection=None,
        prior=[],
    )
    last = msgs[-1]
    assert last["role"] == "user"
    assert "Hello" in last["content"]
    assert "devtools" in last["content"]


def test_build_messages_selection_explain_includes_selection():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="selection_explain",
        title="T", tag="t", summary="s", selection="useEffect(() => {}, [])",
        prior=[],
    )
    last = msgs[-1]
    assert "code from" in last["content"]
    assert "useEffect" in last["content"]


def test_build_messages_selection_qa_includes_selection():
    cfg = PetConfig()
    msgs = build_messages(
        cfg, mode="selection_qa",
        title="T", tag=None, summary=None, selection="some prose",
        prior=[],
    )
    last = msgs[-1]
    assert "highlighted from" in last["content"]
    assert "some prose" in last["content"]


def test_build_messages_truncates_selection_to_max_context_chars():
    cfg = PetConfig()
    cfg.max_context_chars = 50
    long_sel = "x" * 1000
    msgs = build_messages(
        cfg, mode="selection_explain",
        title="T", tag="t", summary="s", selection=long_sel,
        prior=[],
    )
    last_content = msgs[-1]["content"]
    # 50-char cap on selection
    assert "x" * 50 in last_content
    assert "x" * 51 not in last_content


def test_build_messages_prepends_prior_unchanged():
    cfg = PetConfig()
    prior = [
        {"role": "user", "content": "prev_u"},
        {"role": "assistant", "content": "prev_a"},
    ]
    msgs = build_messages(
        cfg, mode="greet",
        title=None, tag=None, summary=None, selection=None,
        prior=prior,
    )
    assert msgs[0] == {"role": "user", "content": "prev_u"}
    assert msgs[1] == {"role": "assistant", "content": "prev_a"}
    assert msgs[2]["role"] == "user"
    assert "tapped on you" in msgs[2]["content"]


def test_build_messages_returns_only_role_content_pairs():
    """Ensure prior turns are stripped of any extra metadata before
    handing to LLM (the gateway/adapter layer expects clean messages)."""
    cfg = PetConfig()
    prior = [
        {"role": "user", "content": "u", "mode": "greet", "post_id": "x"},
        {"role": "assistant", "content": "a", "mode": "greet", "post_id": "x"},
    ]
    msgs = build_messages(
        cfg, mode="greet",
        title=None, tag=None, summary=None, selection=None,
        prior=prior,
    )
    for m in msgs:
        assert set(m.keys()) == {"role", "content"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_prompt_messages.py -v
```
Expected: ImportError — `build_messages` not in `pet_prompt`.

- [ ] **Step 3: Add `build_messages` to pet_prompt.py**

Append to `backend/app/services/pet_prompt.py`:

```python
def build_messages(
    cfg: PetConfig,
    *,
    mode: PetMode,
    title: str | None,
    tag: str | None,
    summary: str | None,
    selection: str | None,
    prior: list[dict],
) -> list[dict]:
    """Compose the messages array for the LLM gateway.

    Returns: prior turns (user/assistant alternating, role+content only)
    followed by a single new user turn whose content is a "scene tag"
    describing what the visitor just did. The system prompt is built
    separately by build_system().
    """
    selection_text = truncate_selection(selection, cfg.max_context_chars) if selection else ""
    title_text = title or ""
    tag_text = tag or ""

    if mode == "greet":
        scene = "(visitor tapped on you)"
    elif mode == "summary_react":
        scene = f'(visitor reading "{title_text}", tag: {tag_text})'
    elif mode == "selection_explain":
        scene = f'(visitor highlighted code from "{title_text}"): {selection_text}'
    elif mode == "selection_qa":
        scene = f'(visitor highlighted from "{title_text}"): {selection_text}'
    else:
        scene = "(visitor summoned you)"

    cleaned_prior = [
        {"role": t.get("role", "user"), "content": t.get("content", "")}
        for t in prior
        if t.get("role") in ("user", "assistant")
    ]
    return [*cleaned_prior, {"role": "user", "content": scene}]
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_prompt_messages.py tests/test_pet_prompt.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/services/pet_prompt.py backend/tests/test_pet_prompt_messages.py
git commit -m "feat(pet): pet_prompt.build_messages composes scene tag + prior turns"
```

---

## Task 5: Adapters + gateway accept messages array

**Files:**
- Modify: `backend/app/services/pet_adapters/openai_compat.py`
- Modify: `backend/app/services/pet_adapters/anthropic.py`
- Modify: `backend/app/services/pet_gateway.py`
- Modify: `backend/tests/test_pet_summon_modes.py` (already mocks gateway — update assertions)
- Test: this task uses existing tests + smoke check

- [ ] **Step 1: Update openai_compat `chat_stream` signature**

In `backend/app/services/pet_adapters/openai_compat.py`, modify `chat_stream` to accept `messages` instead of `user`:

```python
async def chat_stream(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system: str,
    messages: list[dict] | None = None,
    user: str | None = None,  # legacy: wraps to messages=[{"role":"user","content":user}]
    max_tokens: int = 200,
    temperature: float = 0.9,
    extra_body: dict[str, Any] | None = None,
    timeout: float = 30.0,  # noqa: ASYNC109
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[str]:
    """Yield text chunks from a streaming chat/completions call."""
    if messages is None:
        if user is None:
            raise ValueError("either messages or user must be provided")
        messages = [{"role": "user", "content": user}]
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": True,
    }
    if extra_body:
        body.update(extra_body)
    # ... rest of the function unchanged (the streaming + parsing loop)
```

The body of the function (after `if extra_body: body.update(extra_body)`) stays as it is. Only the signature and the body construction change.

- [ ] **Step 2: Update anthropic `chat_stream` signature**

In `backend/app/services/pet_adapters/anthropic.py`, modify:

```python
async def chat_stream(
    *,
    api_key: str,
    model: str,
    system: str,
    messages: list[dict] | None = None,
    user: str | None = None,  # legacy
    max_tokens: int = 200,
    temperature: float = 0.9,
    timeout: float = 30.0,  # noqa: ASYNC109
) -> AsyncIterator[str]:
    """Yield text deltas from streaming messages.create."""
    if messages is None:
        if user is None:
            raise ValueError("either messages or user must be provided")
        messages = [{"role": "user", "content": user}]
    client = anthropic.AsyncAnthropic(api_key=api_key, timeout=timeout)
    async with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=messages,
    ) as stream:
        async for text in stream.text_stream:
            if text:
                yield text
```

- [ ] **Step 3: Update gateway `summon_stream` signature**

In `backend/app/services/pet_gateway.py`, modify `summon_stream`:

```python
async def summon_stream(
    *,
    providers: list[str],
    secrets: dict[str, dict[str, Any]],
    system: str,
    messages: list[dict] | None = None,
    user: str | None = None,  # legacy
    fallback_lines: list[str],
    timeout_per_call: float = 30.0,
) -> AsyncIterator[dict[str, Any]]:
    """Stream from the first working provider. (See spec §3 for events.)"""
    if messages is None:
        if user is None:
            raise ValueError("either messages or user must be provided")
        messages = [{"role": "user", "content": user}]
    for name in providers:
        # ... existing loop body but change `_call_stream(... user=user)` to
        # `_call_stream(... messages=messages)`
```

Also update `_call_stream` to take `messages`:

```python
async def _call_stream(
    *,
    name: str,
    api_key: str,
    model_override: str | None,
    system: str,
    messages: list[dict],
    timeout: float,  # noqa: ASYNC109
) -> AsyncIterator[str]:
    cfg = PROVIDER_REGISTRY[name]
    model = model_override or cfg["default_model"]
    if model is None:
        raise RuntimeError(f"{name}: no model configured (set extra_json.model)")
    if cfg["adapter"] == "openai_compat":
        async for chunk in openai_compat.chat_stream(
            api_key=api_key, base_url=cfg["base_url"], model=model,
            system=system, messages=messages, timeout=timeout,
            extra_body=cfg.get("extra_body"),
        ):
            yield chunk
        return
    if cfg["adapter"] == "anthropic":
        async for chunk in anthropic_adapter.chat_stream(
            api_key=api_key, model=model,
            system=system, messages=messages, timeout=timeout,
        ):
            yield chunk
        return
    raise RuntimeError(f"{name}: unknown adapter {cfg['adapter']!r}")
```

Update the loop body inside `summon_stream` to pass `messages=messages` instead of `user=user`:

```python
        try:
            async for chunk in _call_stream(
                name=name,
                api_key=sec["key"],
                model_override=sec.get("model"),
                system=system,
                messages=messages,
                timeout=timeout_per_call,
            ):
                received_any = True
                yield {"type": "chunk", "text": chunk}
        except Exception as e:  # noqa: BLE001
            ...
```

- [ ] **Step 4: Run existing pet tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_*.py tests/test_admin_pet*.py tests/test_rate_limit_unlimited.py -v 2>&1 | tail -20
```
Expected: existing tests still pass (the legacy `user=` kwarg path keeps working). If any test was directly inspecting the body sent to httpx (e.g. `test_pet_adapter_openai_compat`), it may need its assertion updated to check `messages[1]` (the user message position) instead of body shape — fix in this commit.

- [ ] **Step 5: Smoke-test the running backend (deepseek)**

The backend is auto-reloading via uvicorn `--reload`. Hit the streaming endpoint:

```bash
curl -sN -X POST http://localhost:51820/api/pet/summon/stream \
  -H 'Content-Type: application/json' -d '{}' --max-time 12 2>&1 | head -10
```

Expected: SSE chunks land as before. (The router still passes `user="summon"`, which now wraps internally to a 1-message array — no behavior change yet.)

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/services/pet_adapters/openai_compat.py backend/app/services/pet_adapters/anthropic.py backend/app/services/pet_gateway.py backend/tests/
git commit -m "refactor(pet): adapters + gateway accept messages array (legacy user kwarg preserved)"
```

---

## Task 6: Wire context load + build_messages + post-stream archive

**Files:**
- Modify: `backend/app/routers/public/pet.py`
- Test: `backend/tests/test_pet_summon_stream_history.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pet_summon_stream_history.py`:

```python
import json

import pytest

from app.services import pet_gateway


@pytest.fixture
def captured_streams(monkeypatch):
    """Capture all gateway.summon_stream calls and replay a fixed reply."""
    calls: list[dict] = []

    async def _fake_stream(**kwargs):
        calls.append(kwargs)
        yield {"type": "chunk", "text": "hello "}
        yield {"type": "chunk", "text": "world"}
        yield {"type": "done", "source": "zhipu"}

    monkeypatch.setattr(pet_gateway, "summon_stream", _fake_stream)
    return calls


async def _read_stream(client, payload):
    """POST and read all SSE frames; return list of parsed event dicts."""
    events = []
    async with client.stream(
        "POST", "/api/pet/summon/stream",
        json=payload,
        headers={"Content-Type": "application/json"},
    ) as r:
        assert r.status_code == 200
        buffer = ""
        async for chunk in r.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                for line in frame.split("\n"):
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
    return events


async def test_first_summon_with_no_history_sends_only_current_turn(
    client, captured_streams, fake_post_id,
):
    await _read_stream(client, {})
    assert len(captured_streams) == 1
    msgs = captured_streams[0]["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "tapped on you" in msgs[0]["content"]


async def test_second_summon_includes_first_turns_in_messages(
    client, captured_streams, fake_post_id,
):
    # Need to wait for the first stream's background task to flush ctx.
    # The endpoint awaits the background task before responding to GET
    # so a sequential POST sees the appended history.
    await _read_stream(client, {})
    await _read_stream(client, {})
    assert len(captured_streams) == 2
    msgs2 = captured_streams[1]["messages"]
    # First turn (user + assistant) + current user turn = 3 messages
    assert len(msgs2) == 3
    assert msgs2[0]["role"] == "user"
    assert "tapped on you" in msgs2[0]["content"]
    assert msgs2[1] == {"role": "assistant", "content": "hello world"}
    assert msgs2[2]["role"] == "user"


async def test_history_persists_to_pet_message_after_stream(
    client, captured_streams, fake_post_id,
):
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import PetMessage

    await _read_stream(client, {"post_id": fake_post_id})
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetMessage))).scalars().all()
        # At least one row written (might be more from prior tests' bleed,
        # but let's assert for THIS visitor_hash via simple presence).
        assert len(rows) >= 1
        latest = max(rows, key=lambda r: r.created_at)
        assert latest.species == "cat"
        assert latest.mode in ("greet", "summary_react")
        assert latest.reply == "hello world"
        assert latest.source == "zhipu"
        # Cleanup
        for r in rows:
            await s.delete(r)
        await s.commit()


@pytest.fixture
async def reset_pet_ctx_redis(redis):
    """Clear any pet:ctx:* keys to isolate streaming history tests."""
    keys = await redis.keys("pet:ctx:*")
    for k in keys:
        await redis.delete(k)
    yield
    keys = await redis.keys("pet:ctx:*")
    for k in keys:
        await redis.delete(k)


async def test_rate_limited_does_not_pollute_history(
    client, captured_streams, fake_post_id, reset_pet_ctx_redis,
):
    # Force rate-limited by zeroing the per-min cap via PetConfig override.
    from sqlalchemy import update
    from app.db import AsyncSessionLocal
    from app.models import SiteMeta
    from app.schemas.pet import PetConfig

    cfg = PetConfig(per_ip_per_min=1, per_ip_per_day=1, global_per_day=1)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1)
                        .values(pet_config=cfg.model_dump()))
        await s.commit()

    # First call: ok
    events1 = await _read_stream(client, {})
    # Second call: rate limited
    events2 = await _read_stream(client, {})
    # Pull last event from rate-limited response
    rl_evts = [e for e in events2 if e.get("type") == "rate_limited"]
    assert rl_evts, f"expected rate_limited event, got {events2}"

    # The gateway must NOT have been called for the rate-limited turn.
    assert len(captured_streams) == 1, "gateway should be skipped on rate limit"

    # Now a third successful call: messages should NOT contain the
    # rate-limited canned line (i.e. only the first ok turn shows up).
    cfg2 = PetConfig()  # back to defaults
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1)
                        .values(pet_config=cfg2.model_dump()))
        await s.commit()

    # Clear rate-limit counters
    keys = await redis.keys("rl:pet:*")
    for k in keys:
        await redis.delete(k)

    await _read_stream(client, {})
    msgs3 = captured_streams[1]["messages"]
    # 3 = first ok user + first ok assistant + current user. The
    # rate-limited turn must be absent from history.
    assert len(msgs3) == 3
    contents = [m["content"] for m in msgs3]
    # No canned tired line (e.g. "pets 累了") in the history
    for c in contents[:-1]:
        assert "累了" not in c
        assert "nap" not in c.lower()
```

This test file is dense — adapt the fixture name for `redis` if your conftest exposes it under a different identifier (re-use the same fakeredis fixture from `test_pet_context.py` if needed by importing it via conftest sharing).

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_summon_stream_history.py -v
```
Expected: failures — gateway is called with `user="summon"` (single string) so `messages` kwarg is missing in mock capture.

- [ ] **Step 3: Wire context + messages + archive in router**

In `backend/app/routers/public/pet.py`, modify the streaming endpoint. Find `public_pet_summon_stream` and:

(a) Compute `visitor_hash` once near the top:

```python
from app.services import pet_context

# ... inside public_pet_summon_stream, after `cfg = await _load_pet_config(s)`:
visitor_hash = ip_hash(client_ip_from(request))[:16]
```

(b) Replace `actor_hash = ip_hash(client_ip_from(request))[:12]` with `actor_hash = visitor_hash[:12]` (just to dedupe; actor still uses 12 chars for legacy event_log compat).

Actually — keep `actor_hash` as is (12 chars — backward-compat with existing event_log entries). `visitor_hash` is new and uses 16 chars per spec.

(c) After the `breach is not None` branch (rate_limited), do NOT add to ctx but DO archive:

Update the rate-limited block:

```python
    if breach is not None:
        quip = random.choice(cfg.tired_lines)
        await write_event(
            s, type="pet.summoned", actor=actor_hash,
            meta={"source": "rate_limited", "breach": breach},
        )
        await s.commit()
        # Archive but skip Redis ctx (canned reply must not pollute LLM context).
        try:
            from app.models import PetMessage
            async with AsyncSessionLocal() as s2:
                m = PetMessage(
                    visitor_hash=visitor_hash, species="unknown",
                    mode="rate_limited",
                    system_prompt="(rate-limited; no LLM call)",
                    prior_turns=[],
                    reply=quip, source="rate_limited",
                )
                s2.add(m)
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_rl", error=repr(e))

        async def rate_limited_stream():
            yield _sse({"type": "rate_limited", "text": quip, "breach": breach})

        return StreamingResponse(rate_limited_stream(), media_type="text/event-stream")
```

(d) Load prior turns and build messages:

After computing `system = pet_prompt.build_system(...)`, add:

```python
    prior = []
    try:
        prior = await pet_context.load(redis, visitor_hash, max_turns=cfg.context_window_turns)
    except Exception as e:  # noqa: BLE001
        log.warning("pet_summon_stream.ctx_load_failed", error=repr(e))

    messages = pet_prompt.build_messages(
        cfg, mode=mode,
        title=title, tag=tag_label, summary=summary, selection=selection,
        prior=prior,
    )

    # The current user turn (last in messages) is what we'll persist.
    current_user_turn = messages[-1].copy()
```

(e) Update the disabled-pet branch (no providers / not enabled) to archive too:

```python
    if not cfg.enabled or not cfg.providers:
        quip = random.choice(cfg.fallback_lines)
        await write_event(
            s, type="pet.summoned", actor=actor_hash,
            meta={"source": "fallback", "mode": mode, "species": assigned, "stream": True},
        )
        await s.commit()
        try:
            from app.models import PetMessage
            async with AsyncSessionLocal() as s2:
                m = PetMessage(
                    visitor_hash=visitor_hash, species=assigned,
                    mode=mode, post_id=post_id, title=title, tag_slug=tag_label,
                    summary=summary, selection=selection,
                    system_prompt=system, prior_turns=prior,
                    reply=quip, source="fallback",
                )
                s2.add(m)
                await s2.commit()
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.archive_failed_fallback", error=repr(e))

        async def disabled_stream():
            yield _sse({"type": "meta", "mode": mode, "species": assigned})
            yield _sse({"type": "fallback", "text": quip, "source": "fallback"})

        return StreamingResponse(disabled_stream(), media_type="text/event-stream")
```

(f) Replace the live `summon_stream` call with the messages-array variant + post-stream ctx + archive:

The existing `event_stream` async generator becomes:

```python
    secrets = await _resolve_secrets(s, cfg.providers)
    providers = list(cfg.providers)
    fallback_lines = list(cfg.fallback_lines)

    async def event_stream():
        terminal_source = "fallback"
        accumulated_chunks: list[str] = []
        try:
            yield _sse({"type": "meta", "mode": mode, "species": assigned})
            async for evt in pet_gateway.summon_stream(
                providers=providers,
                secrets=secrets,
                system=system,
                messages=messages,
                fallback_lines=fallback_lines,
            ):
                if evt.get("type") == "chunk":
                    accumulated_chunks.append(evt.get("text", ""))
                yield _sse(evt)
                if evt.get("type") in ("done", "fallback"):
                    terminal_source = evt.get("source", "fallback")
                    break
        except Exception as e:  # noqa: BLE001
            log.warning("pet_summon_stream.error", error=repr(e))
            yield _sse({"type": "error", "message": "stream failed"})

        full_reply = "".join(accumulated_chunks).strip()

        # Update Redis ctx — only for real LLM replies (not fallback).
        if terminal_source not in ("fallback", "rate_limited") and full_reply:
            try:
                await pet_context.append(
                    redis, visitor_hash,
                    user_turn=current_user_turn,
                    assistant_turn={"role": "assistant", "content": full_reply},
                    max_turns=cfg.context_window_turns,
                    ttl_sec=cfg.context_ttl_seconds,
                )
            except Exception as e:  # noqa: BLE001
                log.warning("pet_summon_stream.ctx_append_failed", error=repr(e))

        # Archive every turn (including fallback) to pet_message.
        if full_reply or terminal_source == "fallback":
            archive_reply = full_reply or random.choice(fallback_lines)
            try:
                from app.models import PetMessage
                async with AsyncSessionLocal() as s2:
                    m = PetMessage(
                        visitor_hash=visitor_hash,
                        species=assigned,
                        mode=mode,
                        post_id=post_id,
                        title=title,
                        tag_slug=tag_label,
                        summary=summary,
                        selection=selection,
                        system_prompt=system,
                        prior_turns=prior,
                        reply=archive_reply,
                        source=terminal_source,
                    )
                    s2.add(m)
                    # Also write event_log for parity with the non-streaming endpoint.
                    await write_event(
                        s2, type="pet.summoned", actor=actor_hash,
                        meta={
                            "source": terminal_source, "mode": mode,
                            "species": assigned, "stream": True,
                        },
                    )
                    await s2.commit()
            except Exception as e:  # noqa: BLE001
                log.warning("pet_summon_stream.archive_failed", error=repr(e))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Note: the existing post-stream `write_event` block at the end of `event_stream()` is replaced by the unified archive block above (it now writes both the event_log row AND the pet_message row in the same transaction).

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_pet_summon_stream_history.py tests/test_pet_summon_modes.py tests/test_pet_summon.py -v 2>&1 | tail -20
```
Expected: all pass. The pre-existing `test_pet_summon_modes` test that monkeypatched `pet_gateway.summon` (non-streaming) still works for the non-streaming endpoint; the new streaming history tests cover the streaming path.

- [ ] **Step 5: Smoke-test live backend**

Same curl as before:
```bash
curl -sN -X POST http://localhost:51820/api/pet/summon/stream \
  -H 'Content-Type: application/json' -d '{}' --max-time 12 2>&1 | head -10
```

Then check Postgres got an archive row:
```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env && set +a && uv run python -c "
import asyncio
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models import PetMessage
async def main():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetMessage).order_by(PetMessage.created_at.desc()).limit(3))).scalars().all()
        for r in rows:
            print(f'{r.created_at} {r.species} {r.mode} {r.source} reply={r.reply[:40]!r}')
asyncio.run(main())
"
```
Expected: at least one row from the smoke call.

- [ ] **Step 6: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/routers/public/pet.py backend/tests/test_pet_summon_stream_history.py
git commit -m "feat(pet): /pet/summon/stream loads ctx, builds messages, archives to pet_message"
```

---

## Task 7: Admin GET /pet/conversations (list grouped by visitor)

**Files:**
- Modify: `backend/app/routers/admin/pet.py`
- Test: `backend/tests/test_admin_pet_conversations.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_admin_pet_conversations.py`:

```python
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models import PetMessage

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_pet_messages():
    """Insert 5 pet_message rows across 3 visitors. Yield, then cleanup."""
    now = datetime.now(UTC)
    async with AsyncSession(engine) as s:
        rows = [
            PetMessage(
                visitor_hash="alice000000000aa",
                species="cat", mode="greet",
                system_prompt="x", prior_turns=[],
                reply="alice-1", source="zhipu",
                created_at=now - timedelta(minutes=30),
            ),
            PetMessage(
                visitor_hash="alice000000000aa",
                species="cat", mode="summary_react",
                system_prompt="x", prior_turns=[],
                reply="alice-2", source="zhipu",
                created_at=now - timedelta(minutes=10),
            ),
            PetMessage(
                visitor_hash="bob000000000000b",
                species="dragon", mode="greet",
                system_prompt="x", prior_turns=[],
                reply="bob-1", source="anthropic",
                created_at=now - timedelta(minutes=20),
            ),
            PetMessage(
                visitor_hash="bob000000000000b",
                species="dragon", mode="selection_qa",
                system_prompt="x", prior_turns=[],
                reply="bob-2", source="anthropic",
                created_at=now - timedelta(minutes=5),
            ),
            PetMessage(
                visitor_hash="carol00000000000",
                species="fox", mode="greet",
                system_prompt="x", prior_turns=[],
                reply="carol-1", source="zhipu",
                created_at=now - timedelta(hours=2),
            ),
        ]
        for r in rows:
            s.add(r)
        await s.commit()
        yield rows
        # Cleanup
        for r in rows:
            await s.delete(r)
        await s.commit()


async def test_get_conversations_groups_by_visitor_hash(
    client, admin_token, seed_pet_messages,
):
    r = await client.get("/api/admin/pet/conversations", headers=_hdr(admin_token))
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    # Find our seeded visitors among results
    by_hash = {it["visitor_hash"]: it for it in items}
    assert "alice000000000aa" in by_hash
    assert "bob000000000000b" in by_hash
    assert "carol00000000000" in by_hash
    assert by_hash["alice000000000aa"]["message_count"] == 2
    assert by_hash["bob000000000000b"]["message_count"] == 2
    assert by_hash["carol00000000000"]["message_count"] == 1
    # Most-recent species (alice's latest mode is summary_react with cat)
    assert by_hash["alice000000000aa"]["species"] == "cat"
    # Last reply preview
    assert "alice-2" in by_hash["alice000000000aa"]["last_reply_preview"]


async def test_conversations_ordered_by_last_msg_desc(
    client, admin_token, seed_pet_messages,
):
    r = await client.get("/api/admin/pet/conversations", headers=_hdr(admin_token))
    items = r.json()["items"]
    # Bob's most recent turn was 5 min ago (latest); Alice 10 min; Carol 2h
    seeded_in_order = [it for it in items
                        if it["visitor_hash"] in
                        {"alice000000000aa", "bob000000000000b", "carol00000000000"}]
    hashes = [it["visitor_hash"] for it in seeded_in_order]
    assert hashes == ["bob000000000000b", "alice000000000aa", "carol00000000000"]


async def test_conversations_filter_by_species(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations?species=dragon",
        headers=_hdr(admin_token),
    )
    items = r.json()["items"]
    seeded = [it for it in items
              if it["visitor_hash"] in
              {"alice000000000aa", "bob000000000000b", "carol00000000000"}]
    assert all(it["species"] == "dragon" for it in seeded)
    assert any(it["visitor_hash"] == "bob000000000000b" for it in seeded)


async def test_conversations_pagination(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations?limit=2",
        headers=_hdr(admin_token),
    )
    body = r.json()
    assert len(body["items"]) <= 2
    if body.get("next_cursor"):
        r2 = await client.get(
            f"/api/admin/pet/conversations?limit=2&cursor={body['next_cursor']}",
            headers=_hdr(admin_token),
        )
        # Second page items distinct from first page
        first_hashes = {it["visitor_hash"] for it in body["items"]}
        for it in r2.json()["items"]:
            assert it["visitor_hash"] not in first_hashes


async def test_conversations_requires_auth(client):
    r = await client.get("/api/admin/pet/conversations")
    assert r.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_conversations.py -v
```
Expected: 404 Not Found on `/admin/pet/conversations`.

- [ ] **Step 3: Implement the GET list endpoint**

Add to `backend/app/routers/admin/pet.py`:

```python
import base64
from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, func, literal_column, select

from app.models import PetMessage
```

(Add these imports near the existing ones.)

```python
def _encode_cursor(last_msg_at: datetime, visitor_hash: str) -> str:
    raw = f"{last_msg_at.isoformat()}|{visitor_hash}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, str] | None:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        ts_str, vh = raw.rsplit("|", 1)
        return datetime.fromisoformat(ts_str), vh
    except Exception:
        return None


@router.get("/pet/conversations")
async def list_conversations(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    species: str | None = Query(default=None, max_length=32),
    since: datetime | None = Query(default=None),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """List conversations grouped by visitor_hash, ordered by last_msg_at desc."""
    # Subquery: for each visitor, find latest created_at + that row's id
    inner = (
        select(
            PetMessage.visitor_hash,
            func.max(PetMessage.created_at).label("last_msg_at"),
            func.count(PetMessage.id).label("message_count"),
        )
        .group_by(PetMessage.visitor_hash)
    )
    if species:
        inner = inner.where(PetMessage.species == species)
    if since:
        inner = inner.where(PetMessage.created_at >= since)
    if cursor:
        decoded = _decode_cursor(cursor)
        if decoded is not None:
            ts, vh = decoded
            # Compound cursor: rows older than ts, OR same ts with greater visitor_hash
            inner = inner.having(
                func.max(PetMessage.created_at) < ts
                | and_(
                    func.max(PetMessage.created_at) == ts,
                    PetMessage.visitor_hash > vh,
                )
            )

    inner = inner.order_by(desc("last_msg_at"), PetMessage.visitor_hash).limit(limit + 1)

    rows = (await s.execute(inner)).all()
    items: list[dict[str, Any]] = []
    for row in rows[:limit]:
        # Per-visitor follow-up: latest species + latest reply preview
        latest = (await s.execute(
            select(PetMessage.species, PetMessage.reply, PetMessage.created_at)
            .where(PetMessage.visitor_hash == row.visitor_hash)
            .order_by(desc(PetMessage.created_at))
            .limit(1)
        )).first()
        items.append({
            "visitor_hash": row.visitor_hash,
            "species": latest.species if latest else "unknown",
            "last_msg_at": row.last_msg_at.isoformat(),
            "message_count": int(row.message_count),
            "last_reply_preview": (latest.reply or "")[:80] if latest else "",
        })
    next_cursor = None
    if len(rows) > limit:
        last = items[-1]
        next_cursor = _encode_cursor(
            datetime.fromisoformat(last["last_msg_at"]),
            last["visitor_hash"],
        )
    return {"items": items, "next_cursor": next_cursor}
```

(The two-step query — group-by then per-visitor follow-up — is simpler and good enough at our scale; if the visitor list grows large it can be optimized to a single query with `array_agg + LATERAL`.)

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_conversations.py -v
```
Expected: 5 passed (or filter test 1 may need adjustment depending on ordering — fix any drift inline).

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/routers/admin/pet.py backend/tests/test_admin_pet_conversations.py
git commit -m "feat(pet): admin GET /pet/conversations grouped by visitor_hash"
```

---

## Task 8: Admin GET /pet/conversations/{visitor_hash} (detail)

**Files:**
- Modify: `backend/app/routers/admin/pet.py`
- Test: extend `backend/tests/test_admin_pet_conversations.py`

- [ ] **Step 1: Append the failing test**

In `backend/tests/test_admin_pet_conversations.py`, append:

```python
async def test_get_conversation_detail_returns_messages_oldest_first(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations/alice000000000aa",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert len(items) == 2
    # Oldest first
    assert items[0]["reply"] == "alice-1"
    assert items[1]["reply"] == "alice-2"
    # Includes archive metadata
    assert "system_prompt" in items[0]
    assert "prior_turns" in items[0]


async def test_get_conversation_detail_pagination(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations/alice000000000aa?limit=1",
        headers=_hdr(admin_token),
    )
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["reply"] == "alice-1"
    assert body.get("next_cursor")


async def test_get_conversation_detail_unknown_visitor_empty(
    client, admin_token,
):
    r = await client.get(
        "/api/admin/pet/conversations/nonexistent",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["items"] == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_conversations.py -v
```
Expected: 404 on detail path.

- [ ] **Step 3: Implement the detail endpoint**

Add to `backend/app/routers/admin/pet.py`:

```python
@router.get("/pet/conversations/{visitor_hash}")
async def get_conversation_detail(
    visitor_hash: str,
    limit: int = Query(default=100, ge=1, le=500),
    cursor: int | None = Query(default=None),
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """All messages for one visitor, oldest first, paginated by id ascending."""
    stmt = (
        select(PetMessage)
        .where(PetMessage.visitor_hash == visitor_hash)
        .order_by(PetMessage.created_at, PetMessage.id)
        .limit(limit + 1)
    )
    if cursor is not None:
        stmt = stmt.where(PetMessage.id > cursor)
    rows = (await s.execute(stmt)).scalars().all()
    items = []
    for r in rows[:limit]:
        items.append({
            "id": r.id,
            "visitor_hash": r.visitor_hash,
            "species": r.species,
            "mode": r.mode,
            "post_id": r.post_id,
            "title": r.title,
            "tag_slug": r.tag_slug,
            "summary": r.summary,
            "selection": r.selection,
            "system_prompt": r.system_prompt,
            "prior_turns": r.prior_turns,
            "reply": r.reply,
            "source": r.source,
            "created_at": r.created_at.isoformat(),
        })
    next_cursor = items[-1]["id"] if len(rows) > limit and items else None
    return {"items": items, "next_cursor": next_cursor}
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_conversations.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/routers/admin/pet.py backend/tests/test_admin_pet_conversations.py
git commit -m "feat(pet): admin GET /pet/conversations/{visitor_hash} detail endpoint"
```

---

## Task 9: Admin DELETE /pet/conversations/{visitor_hash}

**Files:**
- Modify: `backend/app/routers/admin/pet.py`
- Test: extend `backend/tests/test_admin_pet_conversations.py`

- [ ] **Step 1: Append the failing test**

```python
async def test_delete_conversation_removes_db_rows(
    client, admin_token, seed_pet_messages,
):
    from sqlalchemy import select as sql_select
    from app.db import AsyncSessionLocal
    from app.models import PetMessage

    r = await client.delete(
        "/api/admin/pet/conversations/alice000000000aa",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 204
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(
            sql_select(PetMessage).where(PetMessage.visitor_hash == "alice000000000aa")
        )).scalars().all()
        assert rows == []
        # Bob's rows should be untouched
        bob = (await s.execute(
            sql_select(PetMessage).where(PetMessage.visitor_hash == "bob000000000000b")
        )).scalars().all()
        assert len(bob) == 2


async def test_delete_conversation_clears_redis_ctx(
    client, admin_token, redis,
):
    from app.services.pet_context import KEY_PREFIX, append

    await append(
        redis, "deleteme00000000",
        user_turn={"role": "user", "content": "hi"},
        assistant_turn={"role": "assistant", "content": "hello"},
    )
    assert await redis.exists(f"{KEY_PREFIX}deleteme00000000") == 1
    r = await client.delete(
        "/api/admin/pet/conversations/deleteme00000000",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 204
    assert await redis.exists(f"{KEY_PREFIX}deleteme00000000") == 0


async def test_delete_nonexistent_returns_204(client, admin_token):
    """Idempotent — DELETE on a never-seen visitor is success."""
    r = await client.delete(
        "/api/admin/pet/conversations/nonexistent00000",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 204


async def test_delete_requires_write_scope(client, admin_token):
    """Admin auth alone is not enough; needs write scope (existing pattern)."""
    # Using the standard admin_token (which has write scope by default for
    # singleton admin login) — this passes. For api-token-based read-only,
    # a 403 is expected. We just verify the existing endpoint works for the
    # primary admin login.
    r = await client.delete(
        "/api/admin/pet/conversations/x",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_conversations.py -v
```
Expected: 405 Method Not Allowed.

- [ ] **Step 3: Implement DELETE**

Add to `backend/app/routers/admin/pet.py`:

```python
from fastapi import status as http_status
from sqlalchemy import delete

from app.redis import get_redis
from app.services import pet_context


@router.delete(
    "/pet/conversations/{visitor_hash}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_scope("write"))],
)
async def delete_conversation(
    visitor_hash: str,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
    redis = Depends(get_redis),
) -> Response:
    await s.execute(
        delete(PetMessage).where(PetMessage.visitor_hash == visitor_hash)
    )
    await s.commit()
    try:
        await pet_context.clear(redis, visitor_hash)
    except Exception:
        pass  # Redis cleanup is best-effort; DB is the source of truth.
    return Response(status_code=http_status.HTTP_204_NO_CONTENT)
```

(`Response` is already imported at the top of the file from FastAPI.)

If `Response` is not yet imported, add `from fastapi import Response` to the existing FastAPI import line.

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest tests/test_admin_pet_conversations.py -v
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add backend/app/routers/admin/pet.py backend/tests/test_admin_pet_conversations.py
git commit -m "feat(pet): admin DELETE /pet/conversations/{visitor_hash}"
```

---

## Task 10: Frontend api/pet.js helpers

**Files:**
- Modify: `src/api/pet.js`

- [ ] **Step 1: Add 3 helpers**

In `src/api/pet.js`, append to the `apiPet` object:

```js
  listConversations(params = {}) {
    const qs = new URLSearchParams();
    if (params.cursor) qs.set('cursor', params.cursor);
    if (params.species) qs.set('species', params.species);
    if (params.since) qs.set('since', params.since);
    if (params.limit) qs.set('limit', String(params.limit));
    const suffix = qs.toString();
    return request(`/pet/conversations${suffix ? '?' + suffix : ''}`);
  },
  getConversation(visitorHash, params = {}) {
    const qs = new URLSearchParams();
    if (params.cursor) qs.set('cursor', String(params.cursor));
    if (params.limit) qs.set('limit', String(params.limit));
    const suffix = qs.toString();
    return request(
      `/pet/conversations/${encodeURIComponent(visitorHash)}${suffix ? '?' + suffix : ''}`,
    );
  },
  deleteConversation(visitorHash) {
    return request(
      `/pet/conversations/${encodeURIComponent(visitorHash)}`,
      { method: 'DELETE' },
    );
  },
```

- [ ] **Step 2: Smoke test in DevTools console**

Open `/admin/pet`, then in console:
```js
const r = await fetch('/api/admin/pet/conversations', { credentials: 'include' });
console.log(await r.json());
```
Expected: `{ items: [...], next_cursor: ... }`.

- [ ] **Step 3: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add src/api/pet.js
git commit -m "feat(pet): admin api helpers for conversations list/detail/delete"
```

---

## Task 11: Admin PetConversations list component

**Files:**
- Create: `src/admin/pet/PetConversations.jsx`
- Test: `src/admin/pet/PetConversations.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
// src/admin/pet/PetConversations.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PetConversations from './PetConversations.jsx';

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    listConversations: vi.fn(async () => ({
      items: [
        {
          visitor_hash: 'abc',
          species: 'cat',
          last_msg_at: new Date().toISOString(),
          message_count: 3,
          last_reply_preview: 'hello world',
        },
      ],
      next_cursor: null,
    })),
  },
}));

describe('PetConversations', () => {
  it('renders the list grouped by visitor', async () => {
    render(
      <MemoryRouter>
        <PetConversations />
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/abc/));
    expect(screen.getByText('cat')).toBeInTheDocument();
    expect(screen.getByText(/3 msgs/)).toBeInTheDocument();
    expect(screen.getByText(/hello world/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npx vitest run src/admin/pet/PetConversations.test.jsx
```
Expected: ImportError on the `PetConversations` module.

- [ ] **Step 3: Implement the component**

Create `src/admin/pet/PetConversations.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiPet } from '../../api/pet.js';

function ago(iso) {
  const t = Date.now() - new Date(iso).getTime();
  const m = Math.floor(t / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}

export default function PetConversations() {
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [species, setSpecies] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hasMore, setHasMore] = useState(false);

  async function loadPage(reset = false) {
    setLoading(true);
    try {
      const params = {};
      if (!reset && cursor) params.cursor = cursor;
      if (species) params.species = species;
      const r = await apiPet.listConversations(params);
      setItems(reset ? r.items : [...items, ...r.items]);
      setCursor(r.next_cursor);
      setHasMore(!!r.next_cursor);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [species]);

  return (
    <div className="form pad">
      <p className="hint">
        All pet conversations grouped by visitor. Click a row to see the full
        message timeline.
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <label>
          species:&nbsp;
          <input
            type="text"
            value={species}
            placeholder="(any)"
            onChange={(e) => setSpecies(e.target.value)}
            style={{ width: 120 }}
          />
        </label>
      </div>
      {error && <div className="err">{error}</div>}
      {loading && items.length === 0 && <div className="hint">loading…</div>}
      <div>
        {items.map((it) => (
          <Link
            key={it.visitor_hash}
            to={`/admin/pet/conversations/${it.visitor_hash}`}
            className="conv-row"
          >
            <div className="conv-row-head">
              <span className="conv-vh">{it.visitor_hash.slice(0, 12)}…</span>
              <span className="conv-species">{it.species}</span>
              <span className="conv-count">{it.message_count} msgs</span>
              <span className="conv-when">{ago(it.last_msg_at)}</span>
            </div>
            <div className="conv-preview">{it.last_reply_preview}</div>
          </Link>
        ))}
      </div>
      {hasMore && (
        <button type="button" onClick={() => loadPage(false)} disabled={loading}>
          {loading ? 'loading…' : 'load more'}
        </button>
      )}
    </div>
  );
}
```

Add corresponding CSS in `src/styles.css` (under the `/* Admin · Pet */` section):

```css
.admin-pet .conv-row {
  display: block;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 4px;
  margin-bottom: 8px;
  background: var(--bg-2);
  text-decoration: none;
  color: var(--fg);
  transition: border-color 0.15s;
}
.admin-pet .conv-row:hover { border-color: var(--accent); }
.admin-pet .conv-row-head {
  display: flex; gap: 12px; font-size: 12px; align-items: baseline;
}
.admin-pet .conv-vh { color: var(--accent); font-family: 'JetBrains Mono', monospace; }
.admin-pet .conv-species { color: var(--accent-2); }
.admin-pet .conv-count { color: var(--fg-3); }
.admin-pet .conv-when { color: var(--fg-3); margin-left: auto; }
.admin-pet .conv-preview {
  color: var(--fg-2); font-size: 12px; margin-top: 4px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npx vitest run
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add src/admin/pet/PetConversations.jsx src/admin/pet/PetConversations.test.jsx src/styles.css
git commit -m "feat(pet): admin PetConversations list component"
```

---

## Task 12: Admin PetConversationDetail component

**Files:**
- Create: `src/admin/pet/PetConversationDetail.jsx`
- Test: `src/admin/pet/PetConversationDetail.test.jsx`

- [ ] **Step 1: Write the failing test**

```jsx
// src/admin/pet/PetConversationDetail.test.jsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import PetConversationDetail from './PetConversationDetail.jsx';

vi.mock('../../api/pet.js', () => ({
  apiPet: {
    getConversation: vi.fn(async () => ({
      items: [
        {
          id: 1, visitor_hash: 'abc', species: 'cat', mode: 'greet',
          post_id: null, title: null, tag_slug: null, summary: null, selection: null,
          system_prompt: 'you are cat', prior_turns: [],
          reply: 'meow hi', source: 'zhipu',
          created_at: '2026-05-02T13:00:00Z',
        },
        {
          id: 2, visitor_hash: 'abc', species: 'cat', mode: 'summary_react',
          post_id: 'hello', title: 'Hello', tag_slug: 'devtools',
          summary: 'a summary', selection: null,
          system_prompt: 'you are cat', prior_turns: [],
          reply: 'interesting article', source: 'zhipu',
          created_at: '2026-05-02T13:01:00Z',
        },
      ],
      next_cursor: null,
    })),
    deleteConversation: vi.fn(async () => null),
  },
}));

describe('PetConversationDetail', () => {
  it('renders messages oldest first', async () => {
    render(
      <MemoryRouter initialEntries={['/admin/pet/conversations/abc']}>
        <Routes>
          <Route path="/admin/pet/conversations/:visitorHash" element={<PetConversationDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/meow hi/));
    const replies = screen.getAllByTestId('reply-text');
    expect(replies[0]).toHaveTextContent('meow hi');
    expect(replies[1]).toHaveTextContent('interesting article');
  });

  it('delete button prompts confirm and calls api', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { apiPet } = await import('../../api/pet.js');
    render(
      <MemoryRouter initialEntries={['/admin/pet/conversations/abc']}>
        <Routes>
          <Route path="/admin/pet/conversations/:visitorHash" element={<PetConversationDetail />} />
        </Routes>
      </MemoryRouter>,
    );
    await waitFor(() => screen.getByText(/meow hi/));
    fireEvent.click(screen.getByText(/delete all/i));
    expect(confirmSpy).toHaveBeenCalled();
    expect(apiPet.deleteConversation).toHaveBeenCalledWith('abc');
    confirmSpy.mockRestore();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npx vitest run src/admin/pet/PetConversationDetail.test.jsx
```
Expected: ImportError.

- [ ] **Step 3: Implement the component**

Create `src/admin/pet/PetConversationDetail.jsx`:

```jsx
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { apiPet } from '../../api/pet.js';

export default function PetConversationDetail() {
  const { visitorHash } = useParams();
  const nav = useNavigate();
  const [items, setItems] = useState([]);
  const [cursor, setCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  async function loadPage(reset = false) {
    setLoading(true);
    try {
      const params = {};
      if (!reset && cursor) params.cursor = cursor;
      const r = await apiPet.getConversation(visitorHash, params);
      setItems(reset ? r.items : [...items, ...r.items]);
      setCursor(r.next_cursor);
      setHasMore(!!r.next_cursor);
      setError(null);
    } catch (e) {
      setError(e?.detail || e?.message || 'failed to load');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadPage(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visitorHash]);

  async function handleDelete() {
    if (!confirm(`Delete ALL messages for ${visitorHash}? This cannot be undone.`)) return;
    try {
      await apiPet.deleteConversation(visitorHash);
      nav('/admin/pet?tab=conversations');
    } catch (e) {
      setError(e?.detail || e?.message || 'delete failed');
    }
  }

  if (loading && items.length === 0) return <div className="hint pad">loading…</div>;
  if (error) return <div className="err pad">{error}</div>;

  return (
    <div className="form pad">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12 }}>
        <h2 style={{ margin: 0, fontSize: 14 }}>
          {visitorHash} · {items.length > 0 && items[0].species} · {items.length} messages
        </h2>
        <span className="grow" />
        <button type="button" onClick={handleDelete} className="danger">
          Delete all
        </button>
      </div>
      <div>
        {items.map((m) => (
          <div key={m.id} className="conv-msg">
            <div className="conv-msg-head">
              <span>{new Date(m.created_at).toLocaleString()}</span>
              <span className="conv-msg-mode">{m.mode}</span>
              {m.post_id && <span className="conv-msg-path">/p/{m.post_id}</span>}
              <span className="grow" />
              <span className="conv-msg-source">[{m.source}]</span>
            </div>
            {m.selection && (
              <div className="conv-msg-sel">
                <code>{m.selection}</code>
              </div>
            )}
            <div className="conv-msg-reply" data-testid="reply-text">
              {m.reply}
            </div>
            <details className="conv-msg-debug">
              <summary>debug</summary>
              <pre>{m.system_prompt}</pre>
              <pre>{JSON.stringify(m.prior_turns, null, 2)}</pre>
            </details>
          </div>
        ))}
      </div>
      {hasMore && (
        <button type="button" onClick={() => loadPage(false)} disabled={loading}>
          {loading ? 'loading…' : 'load older'}
        </button>
      )}
    </div>
  );
}
```

Add CSS to `src/styles.css`:

```css
.admin-pet .conv-msg {
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 10px 12px;
  margin-bottom: 8px;
  background: var(--bg-2);
}
.admin-pet .conv-msg-head {
  display: flex; gap: 10px; font-size: 11px; color: var(--fg-3);
  align-items: center; margin-bottom: 6px;
}
.admin-pet .conv-msg-mode { color: var(--accent); }
.admin-pet .conv-msg-path { color: var(--accent-2); font-family: 'JetBrains Mono', monospace; }
.admin-pet .conv-msg-source { color: var(--fg-4); }
.admin-pet .conv-msg-sel {
  background: var(--bg-3); border-left: 2px solid var(--accent);
  padding: 6px 8px; font-size: 12px; margin-bottom: 6px;
  font-family: 'JetBrains Mono', monospace;
  white-space: pre-wrap; word-break: break-word;
}
.admin-pet .conv-msg-reply { font-size: 13px; color: var(--fg); white-space: pre-wrap; }
.admin-pet .conv-msg-debug { margin-top: 8px; }
.admin-pet .conv-msg-debug summary { color: var(--fg-4); font-size: 11px; cursor: pointer; }
.admin-pet .conv-msg-debug pre {
  background: var(--bg-3); border: 1px solid var(--line);
  padding: 6px 8px; font-size: 11px; overflow-x: auto;
  border-radius: 3px; margin: 4px 0;
}
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npx vitest run
```
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add src/admin/pet/PetConversationDetail.jsx src/admin/pet/PetConversationDetail.test.jsx src/styles.css
git commit -m "feat(pet): admin PetConversationDetail component with debug folds"
```

---

## Task 13: Wire conversations tab into Pet.jsx + add detail route

**Files:**
- Modify: `src/admin/Pet.jsx`
- Modify: `src/admin/index.jsx` (add route for detail page)

- [ ] **Step 1: Modify Pet.jsx tab list**

In `src/admin/Pet.jsx`, locate the `TABS` constant and add:

```jsx
const TABS = [
  { id: 'behavior', label: 'Behavior' },
  { id: 'personas', label: 'Personas' },
  { id: 'templates', label: 'Prompt templates' },
  { id: 'conversations', label: 'Conversations' },
];
```

Import the new component near the top:
```jsx
import PetConversations from './pet/PetConversations.jsx';
```

In the render block, after the existing `{tab === 'templates' && (...)}`:

```jsx
      {tab === 'conversations' && <PetConversations />}
```

- [ ] **Step 2: Add detail route**

In `src/admin/index.jsx`, locate the existing admin routes (e.g., `<Route path="pet" element={<Pet />} />`) and add a sibling:

```jsx
import PetConversationDetail from './pet/PetConversationDetail.jsx';

// inside the Routes:
<Route path="pet/conversations/:visitorHash" element={<PetConversationDetail />} />
```

- [ ] **Step 3: Smoke-test in browser**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npm run dev
```

Navigate to `http://localhost:5173/admin/pet?tab=conversations`. Verify:
1. Conversations tab is visible alongside the others.
2. List loads (or shows "loading…" if no data).
3. Clicking a row navigates to `/admin/pet/conversations/<hash>`.
4. Detail page renders messages chronologically.
5. Delete button prompts and removes the row from the list.

Stop the dev server.

- [ ] **Step 4: Commit**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git add src/admin/Pet.jsx src/admin/index.jsx
git commit -m "feat(pet): admin Conversations tab + detail route wiring"
```

---

## Task 14: e2e smoke + final review + PR

- [ ] **Step 1: Restart backend + dev server**

```bash
# Terminal 1 (backend with reload — uvicorn was already running, but restart fresh):
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env && set +a && uv run uvicorn app.main:app --port 51820 --reload

# Terminal 2 (vite):
cd /Users/sd3/Desktop/project/MyBlog && npm run dev
```

- [ ] **Step 2: Verify pet remembers across summons**

Open `http://localhost:5173/`, hard-refresh to clear any old `pet_id` cookie, then:

1. Click the pet on the homepage → wait for streamed reply A.
2. Within 2 hours, click the pet again → reply B should reference / continue the topic of A (LLM saw A in messages array).

Use DevTools Network tab to confirm `/api/pet/summon/stream` is called and SSE chunks arrive.

- [ ] **Step 3: Verify conversation archive**

From a terminal:
```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env && set +a && uv run python -c "
import asyncio
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models import PetMessage
async def main():
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetMessage).order_by(PetMessage.created_at.desc()).limit(5))).scalars().all()
        for r in rows:
            print(f'{r.created_at} {r.visitor_hash[:8]} {r.species} {r.mode} src={r.source} reply={r.reply[:50]!r}')
asyncio.run(main())
"
```
Expected: rows from your two clicks above.

- [ ] **Step 4: Verify admin Conversations tab**

In the browser, navigate to `http://localhost:5173/admin/pet?tab=conversations`. Verify:
1. Your visitor_hash appears with message_count >= 2.
2. Click into the row → see both messages in chronological order.
3. Click `Delete all` → confirm → returns to list, your row is gone.
4. Click pet again on homepage → fresh archive row appears (tab list refreshed).

- [ ] **Step 5: Run full backend test suite**

```bash
cd /Users/sd3/Desktop/project/MyBlog/backend && set -a && source .env.test && set +a && uv run pytest -q 2>&1 | tail -10
```
Expected: pet-related tests pass; pre-existing unrelated failures (auth_2fa, analytics, etc.) unchanged.

- [ ] **Step 6: Run full frontend test suite**

```bash
cd /Users/sd3/Desktop/project/MyBlog && npx vitest run 2>&1 | tail -8
```
Expected: all pass.

- [ ] **Step 7: Push branch + open PR**

```bash
cd /Users/sd3/Desktop/project/MyBlog && git push -u origin feat/pet-conversation-memory
gh pr create --title "feat(pet): conversation memory — Redis ctx + Postgres archive" --body "$(cat <<'EOF'
## Summary
- 10-turn rolling Redis context per visitor (2h sliding TTL) injected into the LLM messages array
- New \`pet_message\` table for permanent archive of every summon turn (admin-browseable)
- Gateway + adapters upgraded from \`user: str\` to \`messages: list[dict]\` (legacy kwarg preserved for compat)
- Admin \`/admin/pet?tab=conversations\` lists conversations grouped by visitor_hash
- Detail view with debug folds (system_prompt + prior_turns) and \`Delete all\` action
- \`pet_context\` and \`pet_message\` failures degrade gracefully — visitor never sees backend persistence errors

Spec: \`docs/superpowers/specs/2026-05-02-pet-conversation-memory-design.md\`

## Privacy footprint
Acknowledged: \`selection\` text and full \`reply\` are persisted permanently. Documented in spec; mitigations (visitor self-delete, retention prune) deferred to v2.

## Test plan
- [x] Backend pet tests pass
- [x] Frontend tests pass
- [x] Manual: pet remembers across summons; archive in DB; admin tab works; delete clears DB + Redis

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 8: Done**

PR opened. Wait for human review or proceed with the user's approval flow.

---

## Notes for the implementer

- **Branch strategy**: create `feat/pet-conversation-memory` off `main` before starting Task 1.
- **DB session lifecycle in streaming**: the streaming generator uses `AsyncSessionLocal()` directly (NOT the request-scoped `s` from `Depends(get_session)`), because the request session may close before the generator finishes flushing chunks. This is already the pattern in the existing `event_stream` cleanup block.
- **Existing test stability**: prior tests assert specific text in mock-captured `system` strings (e.g., "tapped on you"). Those continue to work — only the gateway's `user` parameter changed to `messages`, the system prompt itself is untouched.
- **Privacy**: when committing, do NOT include any test fixture rows that look like real visitor data. Use obviously-synthetic `visitor_hash` values like `"abc"` or `"alice000000000aa"`.
