# Phase 6a — Media Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship admin-only media library: image upload (multi-file), list, alt edit, delete; FastAPI `StaticFiles` mount serves files publicly; `site_meta.avatar_id` FK links uploaded avatars with `ON DELETE SET NULL`.

**Architecture:** Self-contained filesystem storage under `data/media/{aa}/{uuid}-{name}`. `media_storage` service is a thin adapter (validation, save, delete, url_for) so future S3 swap touches one module. `media` DB service follows the P4 atomicity pattern (service flushes; routers commit). Each file in a batch upload is its own transaction so partial-batch isolation is guaranteed.

**Tech Stack:** FastAPI 0.115+, Pillow 10+, async SQLAlchemy 2.0 + asyncpg, Alembic, Postgres 16, Pydantic v2.

---

## File Map

**Create**
- `backend/alembic/versions/0005_media.py`
- `backend/app/models/media.py`
- `backend/app/schemas/media.py`
- `backend/app/services/media_storage.py`
- `backend/app/services/media.py`
- `backend/app/routers/admin/media.py`
- `backend/tests/test_media_storage.py`
- `backend/tests/test_admin_media.py`
- `backend/tests/test_alembic_0005_roundtrip.py`

**Modify**
- `backend/pyproject.toml` — add `pillow>=10.0`
- `backend/app/models/__init__.py` — register `Media`, export
- `backend/app/models/site_meta.py` — add `avatar_id` FK column
- `backend/app/main.py` — add `StaticFiles` mount
- `backend/app/routers/admin/__init__.py` — register media router

---

## Task 1: Pillow dependency

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add dependency to pyproject.toml**

Open `backend/pyproject.toml` and find the `dependencies = [...]` array. Add `"pillow>=10.0",` keeping alphabetical order (between `passlib` and `pydantic` if those exist, or just append before the closing `]`).

- [ ] **Step 2: Sync**

```bash
cd backend && uv sync --all-extras
```

Expected: `Resolved N packages in ...ms` then `Installed pillow ...`. No errors.

- [ ] **Step 3: Verify import works**

```bash
cd backend && uv run python -c "from PIL import Image; print(Image.__version__)"
```

Expected: a version `10.x.x` or higher prints. If it prints `< 10`, the version pin in step 1 was wrong.

- [ ] **Step 4: Commit**

```bash
cd backend && git add pyproject.toml uv.lock
git commit -m "chore(phase6a): add Pillow for image validation"
```

---

## Task 2: Migration 0005_media

**Files:**
- Create: `backend/alembic/versions/0005_media.py`

- [ ] **Step 1: Write the migration**

```python
"""media

Revision ID: 0005_media
Revises: 0004_integrations

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_media"
down_revision: str | None = "0004_integrations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_media_created_at",
        "media",
        [sa.text("created_at DESC")],
    )

    op.add_column(
        "site_meta",
        sa.Column("avatar_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_site_meta_avatar_id",
        "site_meta",
        "media",
        ["avatar_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_site_meta_avatar_id", "site_meta", type_="foreignkey")
    op.drop_column("site_meta", "avatar_id")
    op.drop_index("ix_media_created_at", table_name="media")
    op.drop_table("media")
```

- [ ] **Step 2: Apply forward**

```bash
cd backend && uv run alembic upgrade head
```

Expected: `Running upgrade 0004_integrations -> 0005_media, media`. No errors.

- [ ] **Step 3: Verify schema**

```bash
docker exec backend-postgres-1 psql -U myblog -d myblog -c "\d media" 2>&1 | head -20
docker exec backend-postgres-1 psql -U myblog -d myblog -c "\d site_meta" 2>&1 | grep avatar_id
```

Expected: `media` shows 9 columns (id, filename, storage_path, mime_type, size, width, height, alt, created_at). `site_meta` shows `avatar_id | integer |`.

- [ ] **Step 4: Round-trip down/up**

```bash
cd backend && uv run alembic downgrade 0004_integrations && uv run alembic upgrade head
```

Expected: clean down then up. No errors.

- [ ] **Step 5: Commit**

```bash
cd backend && git add alembic/versions/0005_media.py
git commit -m "feat(phase6a): 0005 migration (media + site_meta.avatar_id FK)"
```

---

## Task 3: ORM models — Media + SiteMeta.avatar_id

**Files:**
- Create: `backend/app/models/media.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/site_meta.py`

- [ ] **Step 1: Write Media ORM**

Create `backend/app/models/media.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Media(Base):
    __tablename__ = "media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    alt: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

- [ ] **Step 2: Register Media in models/__init__.py**

Open `backend/app/models/__init__.py` and add the import + export:

After `from app.models.like_event import LikeEvent` add:
```python
from app.models.media import Media
```

In `__all__`, add `"Media",` to the list (alphabetically between `"MagicLink"` and `"NowEntry"`).

- [ ] **Step 3: Add avatar_id to SiteMeta**

Open `backend/app/models/site_meta.py`. Update the `from sqlalchemy import` line to include `ForeignKey`:

```python
from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, String, Text
```

Add the new column after `pet_config`:

```python
    avatar_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 4: Verify import + ORM autoload doesn't crash**

```bash
cd backend && uv run python -c "from app.models import Media, SiteMeta; print(Media.__tablename__, [c.name for c in SiteMeta.__table__.columns if c.name == 'avatar_id'])"
```

Expected output: `media ['avatar_id']`

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/models/media.py app/models/__init__.py app/models/site_meta.py
git commit -m "feat(phase6a): ORM models for Media + SiteMeta.avatar_id"
```

---

## Task 4: Pydantic schemas

**Files:**
- Create: `backend/app/schemas/media.py`

- [ ] **Step 1: Write the schemas file**

Create `backend/app/schemas/media.py`:

```python
"""Pydantic schemas for the media admin API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MediaItem(BaseModel):
    id: int
    filename: str
    url: str
    mime_type: str
    size: int
    width: int | None = None
    height: int | None = None
    alt: str | None = None
    created_at: datetime


class MediaPatch(BaseModel):
    alt: str | None = Field(default=None, max_length=512)


class MediaUploadFailure(BaseModel):
    filename: str
    error: str


class MediaUploadResponse(BaseModel):
    ok: list[MediaItem]
    failed: list[MediaUploadFailure]
```

- [ ] **Step 2: Verify imports**

```bash
cd backend && uv run python -c "from app.schemas.media import MediaItem, MediaPatch, MediaUploadResponse, MediaUploadFailure; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/schemas/media.py
git commit -m "feat(phase6a): Pydantic schemas for media admin API"
```

---

## Task 5: media_storage — size + MIME validation (TDD start)

**Files:**
- Create: `backend/app/services/media_storage.py` (skeleton)
- Create: `backend/tests/test_media_storage.py`

- [ ] **Step 1: Write failing tests for size + MIME guard**

Create `backend/tests/test_media_storage.py`:

```python
"""media_storage validation + IO unit tests."""
from __future__ import annotations

import pytest

from app.services.media_storage import (
    ALLOWED_MIME,
    MAX_BYTES,
    MediaError,
    save,
)


async def test_save_rejects_too_large():
    big = b"x" * (MAX_BYTES + 1)
    with pytest.raises(MediaError, match="too large"):
        await save(big, declared_mime="image/png", original_name="big.png")


async def test_save_rejects_unsupported_mime():
    with pytest.raises(MediaError, match="unsupported mime"):
        await save(b"%PDF-1.4...", declared_mime="application/pdf", original_name="doc.pdf")


def test_allowed_mime_set_is_exhaustive():
    """Tighten this test if the spec ever changes the whitelist."""
    assert ALLOWED_MIME == {
        "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
    }
```

- [ ] **Step 2: Run — expect ImportError**

```bash
cd backend && uv run pytest tests/test_media_storage.py -x 2>&1 | tail -15
```

Expected: `ModuleNotFoundError: No module named 'app.services.media_storage'`.

- [ ] **Step 3: Write minimal media_storage.py**

Create `backend/app/services/media_storage.py`:

```python
"""Media filesystem adapter: validation, save, delete, url_for."""
from __future__ import annotations


class MediaError(Exception):
    """Raised when an upload fails validation."""


ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


async def save(content: bytes, *, declared_mime: str, original_name: str):
    if len(content) > MAX_BYTES:
        raise MediaError("too large, max 10MB")
    if declared_mime not in ALLOWED_MIME:
        raise MediaError(f"unsupported mime: {declared_mime}")
    raise NotImplementedError("further validation not yet implemented")
```

- [ ] **Step 4: Run — expect 3 PASS**

```bash
cd backend && uv run pytest tests/test_media_storage.py -x 2>&1 | tail -10
```

Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/media_storage.py tests/test_media_storage.py
git commit -m "feat(phase6a): media_storage size + MIME guard"
```

---

## Task 6: media_storage — Pillow raster validation + canonical MIME

**Files:**
- Modify: `backend/app/services/media_storage.py`
- Modify: `backend/tests/test_media_storage.py`

- [ ] **Step 1: Write failing tests for Pillow validation**

Append to `backend/tests/test_media_storage.py`:

```python
from io import BytesIO
from PIL import Image


def _png_bytes(w: int = 4, h: int = 3) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 128, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int = 5, h: int = 7) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 0, 200)).save(buf, format="JPEG")
    return buf.getvalue()


async def test_save_accepts_png_with_dims(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    res = await media_storage.save(
        _png_bytes(w=10, h=20), declared_mime="image/png", original_name="cat.png"
    )
    assert res.mime_type == "image/png"
    assert res.width == 10
    assert res.height == 20
    assert res.size == len(_png_bytes(w=10, h=20))


async def test_save_canonicalizes_mime_when_extension_lies(tmp_path, monkeypatch):
    """Declared image/png but bytes are JPEG → canonicalized to image/jpeg."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    jpeg = _jpeg_bytes(w=5, h=7)
    res = await media_storage.save(
        jpeg, declared_mime="image/png", original_name="liar.png"
    )
    assert res.mime_type == "image/jpeg"


async def test_save_rejects_decode_failure(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    with pytest.raises(MediaError, match="not a valid image"):
        await media_storage.save(
            b"definitely not an image",
            declared_mime="image/png",
            original_name="garbage.png",
        )
```

- [ ] **Step 2: Run — expect failure**

```bash
cd backend && uv run pytest tests/test_media_storage.py -x 2>&1 | tail -15
```

Expected: tests fail (NotImplementedError or AttributeError on `MEDIA_DIR`).

- [ ] **Step 3: Implement Pillow path + actual save**

Replace `backend/app/services/media_storage.py` with:

```python
"""Media filesystem adapter: validation, save, delete, url_for."""
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import get_settings


class MediaError(Exception):
    """Raised when an upload fails validation."""


ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Pillow's `format` strings → canonical mime types.
_PIL_FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}

# Tests override this to point at a tmpdir.
MEDIA_DIR: Path = get_settings().data_dir / "media"


@dataclass
class SaveResult:
    storage_path: str
    mime_type: str
    size: int
    width: int | None
    height: int | None


def url_for(storage_path: str) -> str:
    """Return the public URL for a stored asset. S3 swap changes only this."""
    return f"/media/{storage_path}"


async def save(
    content: bytes, *, declared_mime: str, original_name: str
) -> SaveResult:
    if len(content) > MAX_BYTES:
        raise MediaError("too large, max 10MB")
    if declared_mime not in ALLOWED_MIME:
        raise MediaError(f"unsupported mime: {declared_mime}")

    if declared_mime == "image/svg+xml":
        # SVG path is implemented in Task 7.
        raise NotImplementedError("svg path implemented in next task")

    try:
        img = Image.open(BytesIO(content))
        img.load()  # force decode so corrupt files raise here
    except (UnidentifiedImageError, OSError) as e:
        raise MediaError(f"not a valid image: {e}") from e

    canonical = _PIL_FORMAT_TO_MIME.get(img.format)
    if canonical is None:
        raise MediaError(f"unsupported pil format: {img.format}")

    storage_path = _build_storage_path(original_name, canonical)
    full = MEDIA_DIR / storage_path
    full.parent.mkdir(parents=True, exist_ok=True)
    tmp = full.with_suffix(full.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.rename(full)

    return SaveResult(
        storage_path=storage_path,
        mime_type=canonical,
        size=len(content),
        width=img.width,
        height=img.height,
    )


def _build_storage_path(original_name: str, mime_type: str) -> str:
    """Bucket prefix from UUID → "7f/7f3e1abc-orig.png"."""
    safe_name = "".join(
        c for c in original_name if c.isalnum() or c in ("-", "_", ".")
    ) or "file"
    new_uuid = uuid.uuid4().hex
    bucket = new_uuid[:2]
    return f"{bucket}/{new_uuid}-{safe_name}"
```

- [ ] **Step 4: Run — expect PASS**

```bash
cd backend && uv run pytest tests/test_media_storage.py -x 2>&1 | tail -10
```

Expected: `6 passed` (3 original + 3 new).

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/media_storage.py tests/test_media_storage.py
git commit -m "feat(phase6a): Pillow validation + canonical MIME"
```

---

## Task 7: media_storage — SVG XML scan

**Files:**
- Modify: `backend/app/services/media_storage.py`
- Modify: `backend/tests/test_media_storage.py`

- [ ] **Step 1: Write failing tests for SVG paths**

Append to `backend/tests/test_media_storage.py`:

```python
SVG_OK = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><circle cx="5" cy="5" r="4"/></svg>'
SVG_SCRIPT = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
SVG_ONLOAD = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect/></svg>'


async def test_save_accepts_clean_svg(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    res = await media_storage.save(
        SVG_OK, declared_mime="image/svg+xml", original_name="icon.svg"
    )
    assert res.mime_type == "image/svg+xml"
    assert res.width is None
    assert res.height is None


async def test_save_rejects_svg_with_script(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    with pytest.raises(MediaError, match="svg with script"):
        await media_storage.save(
            SVG_SCRIPT, declared_mime="image/svg+xml", original_name="bad.svg"
        )


async def test_save_rejects_svg_with_onload(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    with pytest.raises(MediaError, match="svg with script"):
        await media_storage.save(
            SVG_ONLOAD, declared_mime="image/svg+xml", original_name="bad.svg"
        )
```

- [ ] **Step 2: Run — expect NotImplementedError on the OK case + failures on others**

```bash
cd backend && uv run pytest tests/test_media_storage.py -k svg -x 2>&1 | tail -15
```

Expected: at least one `NotImplementedError` or assertion failure.

- [ ] **Step 3: Implement SVG branch**

In `backend/app/services/media_storage.py`, replace the SVG `raise NotImplementedError(...)` block with:

```python
    if declared_mime == "image/svg+xml":
        _validate_svg(content)
        storage_path = _build_storage_path(original_name, "image/svg+xml")
        full = MEDIA_DIR / storage_path
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp = full.with_suffix(full.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.rename(full)
        return SaveResult(
            storage_path=storage_path,
            mime_type="image/svg+xml",
            size=len(content),
            width=None,
            height=None,
        )
```

Then add this helper at module bottom:

```python
def _validate_svg(content: bytes) -> None:
    """Reject SVGs containing <script> elements or `on*` event-handler attributes."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise MediaError(f"invalid svg xml: {e}") from e
    for el in root.iter():
        # local tag name strips XML namespace, e.g. "{ns}script" → "script".
        local = el.tag.rsplit("}", 1)[-1].lower()
        if local == "script":
            raise MediaError("svg with script content not allowed")
        for attr in el.attrib:
            local_attr = attr.rsplit("}", 1)[-1].lower()
            if local_attr.startswith("on"):
                raise MediaError("svg with script content not allowed")
    # also catch top-level on* on the root itself (covered by the loop above
    # since the iterator yields the root).
```

- [ ] **Step 4: Run all media_storage tests — expect 9 PASS**

```bash
cd backend && uv run pytest tests/test_media_storage.py -x 2>&1 | tail -10
```

Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/media_storage.py tests/test_media_storage.py
git commit -m "feat(phase6a): media_storage SVG XML scan (script + on* guard)"
```

---

## Task 8: media_storage — delete + idempotence

**Files:**
- Modify: `backend/app/services/media_storage.py`
- Modify: `backend/tests/test_media_storage.py`

- [ ] **Step 1: Write failing tests for delete**

Append to `backend/tests/test_media_storage.py`:

```python
async def test_delete_removes_file(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    res = await media_storage.save(
        _png_bytes(), declared_mime="image/png", original_name="x.png"
    )
    full = tmp_path / res.storage_path
    assert full.exists()
    await media_storage.delete(res.storage_path)
    assert not full.exists()


async def test_delete_is_idempotent(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    # Should not raise even though the file was never created.
    await media_storage.delete("aa/never-existed.png")


def test_url_for_returns_media_prefix():
    from app.services.media_storage import url_for
    assert url_for("7f/7f3e-cat.png") == "/media/7f/7f3e-cat.png"
```

- [ ] **Step 2: Run — expect AttributeError on `delete`**

```bash
cd backend && uv run pytest tests/test_media_storage.py -k "delete or url_for" -x 2>&1 | tail -10
```

Expected: `AttributeError: module 'app.services.media_storage' has no attribute 'delete'`. The `url_for` test should pass.

- [ ] **Step 3: Implement delete**

Append to `backend/app/services/media_storage.py`:

```python
async def delete(storage_path: str) -> None:
    """Remove the stored file. No-op if already missing."""
    full = MEDIA_DIR / storage_path
    try:
        full.unlink()
    except FileNotFoundError:
        return
```

- [ ] **Step 4: Run all storage tests — expect 12 PASS**

```bash
cd backend && uv run pytest tests/test_media_storage.py -x 2>&1 | tail -10
```

Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/media_storage.py tests/test_media_storage.py
git commit -m "feat(phase6a): media_storage delete (idempotent) + url_for"
```

---

## Task 9: media DB service

**Files:**
- Create: `backend/app/services/media.py`

- [ ] **Step 1: Write the service**

Create `backend/app/services/media.py`:

```python
"""Media DB service. Service flushes; routers commit (P4 atomicity invariant)."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Media
from app.services.media_storage import SaveResult


async def list_all(s: AsyncSession, *, limit: int = 100) -> list[Media]:
    return list(
        (
            await s.execute(
                select(Media).order_by(Media.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def get(s: AsyncSession, *, media_id: int) -> Media | None:
    return (
        await s.execute(select(Media).where(Media.id == media_id))
    ).scalar_one_or_none()


async def create(
    s: AsyncSession,
    *,
    save_result: SaveResult,
    original_filename: str,
    alt: str | None = None,
) -> Media:
    row = Media(
        filename=original_filename,
        storage_path=save_result.storage_path,
        mime_type=save_result.mime_type,
        size=save_result.size,
        width=save_result.width,
        height=save_result.height,
        alt=alt,
        created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.flush()
    await s.refresh(row)
    return row


async def patch_alt(
    s: AsyncSession, *, media_id: int, alt: str | None
) -> Media | None:
    row = await get(s, media_id=media_id)
    if row is None:
        return None
    row.alt = alt
    await s.flush()
    await s.refresh(row)
    return row


async def delete_one(
    s: AsyncSession, *, media_id: int
) -> tuple[bool, str | None]:
    """Returns (was_deleted, storage_path).
    Caller commits the row delete first, THEN unlinks the file —
    so a crash leaves an orphan file (cleanable later) instead of a row pointing at nothing."""
    row = await get(s, media_id=media_id)
    if row is None:
        return False, None
    storage_path = row.storage_path
    await s.execute(delete(Media).where(Media.id == media_id))
    await s.flush()
    return True, storage_path
```

- [ ] **Step 2: Verify import works**

```bash
cd backend && uv run python -c "from app.services.media import list_all, get, create, patch_alt, delete_one; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/services/media.py
git commit -m "feat(phase6a): media DB service"
```

---

## Task 10: StaticFiles mount in main.py

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Edit main.py**

Open `backend/app/main.py`. After the line `app.include_router(admin_router)` add (and update imports at the top):

At the top imports (alphabetically):

```python
from fastapi.staticfiles import StaticFiles
```

In `create_app()` after `app.include_router(admin_router)`:

```python
    media_dir = settings.data_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir), check_dir=False), name="media")
```

- [ ] **Step 2: Boot the app to verify no crash**

```bash
cd backend && uv run python -c "from app.main import create_app; app = create_app(); print('mounted:', any(r.path == '/media' for r in app.routes))"
```

Expected: `mounted: True`. If `False`, the mount call is misplaced.

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/main.py
git commit -m "feat(phase6a): mount StaticFiles at /media"
```

---

## Task 11: Admin router skeleton + GET routes

**Files:**
- Create: `backend/app/routers/admin/media.py`
- Modify: `backend/app/routers/admin/__init__.py`
- Create: `backend/tests/test_admin_media.py`

- [ ] **Step 1: Write failing GET tests**

Create `backend/tests/test_admin_media.py`:

```python
import pytest
from sqlalchemy import delete

from app.db import AsyncSessionLocal
from app.models import Media

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose engine pool between tests so asyncpg connections aren't shared
    across event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


@pytest.fixture
async def cleanup_media():
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Media))
        await s.commit()


async def test_media_list_unauthenticated_401(client, cleanup_media):
    r = await client.get("/api/admin/media")
    assert r.status_code == 401


async def test_media_list_empty(client, admin_token, cleanup_media):
    r = await client.get(
        "/api/admin/media",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json() == []


async def test_media_get_single_404_when_missing(client, admin_token, cleanup_media):
    r = await client.get(
        "/api/admin/media/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect failures (route not registered)**

```bash
cd backend && uv run pytest tests/test_admin_media.py -x 2>&1 | tail -15
```

Expected: all three tests fail. Until the router is registered, FastAPI returns 404 for unregistered paths — so the 401 assertion sees 404, the 200 assertion sees 404, the 404 assertion happens to pass by coincidence (but Step 5 will re-verify it).

- [ ] **Step 3: Write the router**

Create `backend/app/routers/admin/media.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin
from app.models import Account, Media
from app.schemas.media import MediaItem
from app.services import media as media_svc
from app.services.media_storage import url_for

router = APIRouter()


def _to_item(row: Media) -> MediaItem:
    return MediaItem(
        id=row.id,
        filename=row.filename,
        url=url_for(row.storage_path),
        mime_type=row.mime_type,
        size=row.size,
        width=row.width,
        height=row.height,
        alt=row.alt,
        created_at=row.created_at,
    )


@router.get("/media", response_model=list[MediaItem])
async def list_media(
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> list[MediaItem]:
    return [_to_item(r) for r in await media_svc.list_all(s)]


@router.get("/media/{media_id}", response_model=MediaItem)
async def get_media(
    media_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> MediaItem:
    row = await media_svc.get(s, media_id=media_id)
    if row is None:
        raise HTTPException(404, "media not found")
    return _to_item(row)
```

- [ ] **Step 4: Register the router**

In `backend/app/routers/admin/__init__.py`, add the import (alphabetical):

```python
from app.routers.admin.media import router as media_router
```

And below, after the existing `router.include_router(...)` lines (e.g. after `now_admin_router`):

```python
router.include_router(media_router, tags=["admin·media"])
```

- [ ] **Step 5: Run all media tests — expect PASS**

```bash
cd backend && uv run pytest tests/test_admin_media.py -x 2>&1 | tail -10
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```bash
cd backend && git add app/routers/admin/media.py app/routers/admin/__init__.py tests/test_admin_media.py
git commit -m "feat(phase6a): admin media router (GET list + GET single)"
```

---

## Task 12: Admin router — PATCH alt

**Files:**
- Modify: `backend/app/routers/admin/media.py`
- Modify: `backend/tests/test_admin_media.py`

- [ ] **Step 1: Write failing PATCH test**

Append to `backend/tests/test_admin_media.py`:

```python
from datetime import UTC, datetime


async def _seed_media(s, *, filename="cat.png", storage_path="aa/cat.png",
                       mime="image/png", size=100, alt=None) -> int:
    row = Media(
        filename=filename, storage_path=storage_path, mime_type=mime, size=size,
        width=10, height=10, alt=alt, created_at=datetime.now(UTC),
    )
    s.add(row)
    await s.flush()
    return row.id


async def test_media_patch_alt_updates(client, admin_token, cleanup_media):
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, alt=None)
        await s.commit()
    r = await client.patch(
        f"/api/admin/media/{mid}",
        json={"alt": "a small cat"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    assert r.json()["alt"] == "a small cat"


async def test_media_patch_alt_404(client, admin_token, cleanup_media):
    r = await client.patch(
        "/api/admin/media/99999",
        json={"alt": "x"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect 405 / 404 / failure**

```bash
cd backend && uv run pytest tests/test_admin_media.py -k patch -x 2>&1 | tail -15
```

Expected: routes 405 because PATCH not registered.

- [ ] **Step 3: Add PATCH route**

In `backend/app/routers/admin/media.py`, update imports + add the endpoint.

Change the imports block to:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_admin, require_scope
from app.models import Account, Media
from app.schemas.media import MediaItem, MediaPatch
from app.services import media as media_svc
from app.services.event_log import write_event
from app.services.media_storage import url_for
```

Append after `get_media` route:

```python
@router.patch(
    "/media/{media_id}",
    response_model=MediaItem,
    dependencies=[Depends(require_scope("write"))],
)
async def patch_media(
    media_id: int,
    req: MediaPatch,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> MediaItem:
    existing = await media_svc.get(s, media_id=media_id)
    if existing is None:
        raise HTTPException(404, "media not found")
    old_alt = existing.alt
    row = await media_svc.patch_alt(s, media_id=media_id, alt=req.alt)
    await write_event(
        s, type="media.alt_updated", actor=_admin.email,
        target=str(media_id), meta={"id": media_id, "old": old_alt, "new": req.alt},
    )
    await s.commit()
    return _to_item(row)
```

- [ ] **Step 4: Run media tests — expect PASS**

```bash
cd backend && uv run pytest tests/test_admin_media.py -x 2>&1 | tail -10
```

Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/admin/media.py tests/test_admin_media.py
git commit -m "feat(phase6a): PATCH /admin/media/:id alt + event_log"
```

---

## Task 13: Admin router — DELETE + FK SET NULL verification

**Files:**
- Modify: `backend/app/routers/admin/media.py`
- Modify: `backend/tests/test_admin_media.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_admin_media.py`:

```python
from sqlalchemy import select, update
from app.models import SiteMeta


async def test_media_delete_removes_row(client, admin_token, cleanup_media, tmp_path, monkeypatch):
    """Insert a Media row pointing at a path that doesn't exist on disk;
    DELETE should remove the row + idempotently no-op on the missing file."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s, storage_path="aa/never-on-disk.png")
        await s.commit()

    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    async with AsyncSessionLocal() as s:
        gone = (await s.execute(select(Media).where(Media.id == mid))).scalar_one_or_none()
        assert gone is None


async def test_media_delete_404(client, admin_token, cleanup_media):
    r = await client.delete(
        "/api/admin/media/99999",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404


async def test_media_delete_clears_avatar_id_via_fk(client, admin_token, cleanup_media):
    """site_meta.avatar_id = id; DELETE media → avatar_id becomes NULL via ON DELETE SET NULL."""
    async with AsyncSessionLocal() as s:
        mid = await _seed_media(s)
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=mid))
        await s.commit()

    r = await client.delete(
        f"/api/admin/media/{mid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 204

    async with AsyncSessionLocal() as s:
        site = (await s.execute(select(SiteMeta).where(SiteMeta.id == 1))).scalar_one()
        assert site.avatar_id is None
        # Cleanup so the next test sees a clean fixture.
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(avatar_id=None))
        await s.commit()
```

- [ ] **Step 2: Run — expect 405 (DELETE not registered)**

```bash
cd backend && uv run pytest tests/test_admin_media.py -k delete -x 2>&1 | tail -15
```

Expected: failures because DELETE route doesn't exist.

- [ ] **Step 3: Implement DELETE**

In `backend/app/routers/admin/media.py`, change the imports to add `Response`:

```python
from fastapi import APIRouter, Depends, HTTPException, Response
```

Append after `patch_media`:

```python
@router.delete(
    "/media/{media_id}",
    status_code=204,
    dependencies=[Depends(require_scope("write"))],
)
async def delete_media(
    media_id: int,
    _admin: Account = Depends(current_admin),
    s: AsyncSession = Depends(get_session),
) -> Response:
    existing = await media_svc.get(s, media_id=media_id)
    if existing is None:
        raise HTTPException(404, "media not found")
    filename = existing.filename
    was_deleted, storage_path = await media_svc.delete_one(s, media_id=media_id)
    if not was_deleted:
        raise HTTPException(404, "media not found")
    await write_event(
        s, type="media.deleted", actor=_admin.email,
        target=str(media_id),
        meta={"id": media_id, "filename": filename, "storage_path": storage_path},
    )
    await s.commit()

    # File unlink AFTER commit: a crash mid-call leaves an orphan file (cleanable),
    # never a DB row pointing to a missing file.
    if storage_path is not None:
        from app.services.media_storage import delete as fs_delete
        await fs_delete(storage_path)

    return Response(status_code=204)
```

- [ ] **Step 4: Run media tests — expect PASS**

```bash
cd backend && uv run pytest tests/test_admin_media.py -x 2>&1 | tail -10
```

Expected: `8 passed`.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/admin/media.py tests/test_admin_media.py
git commit -m "feat(phase6a): DELETE /admin/media/:id + FK SET NULL coverage"
```

---

## Task 14: POST batch upload with per-file isolation

**Files:**
- Modify: `backend/app/routers/admin/media.py`
- Modify: `backend/tests/test_admin_media.py`

- [ ] **Step 1: Write failing tests**

Append to `backend/tests/test_admin_media.py`:

```python
from io import BytesIO
from PIL import Image


def _png_bytes(w=4, h=3) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 200, 0)).save(buf, format="PNG")
    return buf.getvalue()


async def test_media_post_single_png(client, admin_token, cleanup_media, tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)

    files = {"files": ("cat.png", _png_bytes(20, 30), "image/png")}
    r = await client.post(
        "/api/admin/media",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["ok"]) == 1
    assert body["failed"] == []
    item = body["ok"][0]
    assert item["mime_type"] == "image/png"
    assert item["width"] == 20
    assert item["height"] == 30


async def test_media_post_partial_failure(client, admin_token, cleanup_media, tmp_path, monkeypatch):
    """Two valid PNGs + one oversize. ok=2, failed=1, no abort."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)

    big = b"\x89PNG\r\n\x1a\n" + b"x" * (media_storage.MAX_BYTES + 10)
    files = [
        ("files", ("a.png", _png_bytes(), "image/png")),
        ("files", ("huge.png", big, "image/png")),
        ("files", ("b.png", _png_bytes(), "image/png")),
    ]
    r = await client.post(
        "/api/admin/media",
        files=files,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["ok"]) == 2
    assert len(body["failed"]) == 1
    assert body["failed"][0]["filename"] == "huge.png"
    assert "too large" in body["failed"][0]["error"]


async def test_media_post_unauthenticated_401(client, cleanup_media):
    files = {"files": ("x.png", b"abc", "image/png")}
    r = await client.post("/api/admin/media", files=files)
    assert r.status_code == 401
```

- [ ] **Step 2: Run — expect 405 (POST not registered)**

```bash
cd backend && uv run pytest tests/test_admin_media.py -k post -x 2>&1 | tail -15
```

Expected: failures because POST route doesn't exist.

- [ ] **Step 3: Implement POST batch with per-file isolation**

In `backend/app/routers/admin/media.py`, update imports:

```python
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal, get_session
from app.deps import current_admin, require_scope
from app.models import Account, Media
from app.schemas.media import (
    MediaItem,
    MediaPatch,
    MediaUploadFailure,
    MediaUploadResponse,
)
from app.services import media as media_svc
from app.services.event_log import write_event
from app.services.media_storage import MediaError, url_for
```

Append after `delete_media`:

```python
@router.post(
    "/media",
    response_model=MediaUploadResponse,
    dependencies=[Depends(require_scope("write"))],
)
async def upload_media(
    files: list[UploadFile],
    _admin: Account = Depends(current_admin),
) -> MediaUploadResponse:
    from app.services import media_storage

    ok: list[MediaItem] = []
    failed: list[MediaUploadFailure] = []

    for f in files:
        original = f.filename or "unnamed"
        declared = f.content_type or "application/octet-stream"
        content = await f.read()

        try:
            save_result = await media_storage.save(
                content, declared_mime=declared, original_name=original
            )
        except MediaError as e:
            failed.append(MediaUploadFailure(filename=original, error=str(e)))
            continue
        except Exception as e:  # noqa: BLE001
            failed.append(
                MediaUploadFailure(filename=original, error=f"internal: {e}")
            )
            continue

        # Per-file transaction: insert + event_log + commit. If commit fails,
        # roll back the disk write so we don't leak orphans.
        try:
            async with AsyncSessionLocal() as s2:
                row = await media_svc.create(
                    s2, save_result=save_result, original_filename=original
                )
                await write_event(
                    s2, type="media.uploaded", actor=_admin.email,
                    target=str(row.id),
                    meta={
                        "filename": original,
                        "size": save_result.size,
                        "mime": save_result.mime_type,
                        "width": save_result.width,
                        "height": save_result.height,
                    },
                )
                await s2.commit()
                row_id = row.id
                row_filename = row.filename
                row_mime = row.mime_type
                row_size = row.size
                row_w = row.width
                row_h = row.height
                row_alt = row.alt
                row_created = row.created_at
                row_storage = row.storage_path
        except Exception as e:  # noqa: BLE001
            await media_storage.delete(save_result.storage_path)
            failed.append(
                MediaUploadFailure(filename=original, error=f"db error: {e}")
            )
            continue

        ok.append(
            MediaItem(
                id=row_id,
                filename=row_filename,
                url=url_for(row_storage),
                mime_type=row_mime,
                size=row_size,
                width=row_w,
                height=row_h,
                alt=row_alt,
                created_at=row_created,
            )
        )

    return MediaUploadResponse(ok=ok, failed=failed)
```

- [ ] **Step 4: Run all media tests — expect PASS**

```bash
cd backend && uv run pytest tests/test_admin_media.py -x 2>&1 | tail -10
```

Expected: `11 passed`.

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/admin/media.py tests/test_admin_media.py
git commit -m "feat(phase6a): POST /admin/media batch upload with per-file isolation"
```

---

## Task 15: Migration round-trip test

**Files:**
- Create: `backend/tests/test_alembic_0005_roundtrip.py`

- [ ] **Step 1: Write the test**

Create `backend/tests/test_alembic_0005_roundtrip.py`:

```python
"""Round-trip alembic to 0004 and back to 0005 to exercise the downgrade."""
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


def test_0005_downgrade_then_upgrade_clean():
    # Down to 0004: drops media + site_meta.avatar_id.
    down = _alembic("downgrade", "0004_integrations")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"

    up = _alembic("upgrade", "head")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0005_media" in cur.stdout
```

- [ ] **Step 2: Run**

```bash
cd backend && uv run pytest tests/test_alembic_0005_roundtrip.py -v 2>&1 | tail -10
```

Expected: `1 passed`.

- [ ] **Step 3: Commit**

```bash
cd backend && git add tests/test_alembic_0005_roundtrip.py
git commit -m "test(phase6a): alembic 0005 round-trip"
```

---

## Task 16: Final full-suite + ruff + manual smoke

**Files:**
- (No new files)

- [ ] **Step 1: Full test suite**

```bash
cd backend && uv run pytest 2>&1 | tail -3
```

Expected: total tests ≥ 277 (260 baseline + 12 storage + ≥3 admin GET + ≥2 PATCH + ≥3 DELETE + ≥3 POST = ≥273 minimum; round-trip = +1; Pillow tests where placeholder file path matters might add or subtract a couple). All passing.

- [ ] **Step 2: ruff**

```bash
cd backend && uv run ruff check . 2>&1 | tail -5
```

Expected: no NEW P6a-introduced errors. The 8 pre-existing P3/P4/P5 baseline errors are tolerated (same set as `phase5-integrations` final-review batch).

- [ ] **Step 3: Manual smoke — upload via curl**

Make sure the dev server is running (`uv run uvicorn app.main:app --reload --port 51820` in another terminal). Get an admin token first by hand-logging in, then:

```bash
TOKEN="..."  # paste an /api/admin/auth/login bearer
echo "fake png" > /tmp/p6a.png
# generate a real PNG instead so Pillow accepts it:
uv run python -c "from PIL import Image; Image.new('RGB', (40, 30), 'green').save('/tmp/p6a.png', 'PNG')"

curl -s -X POST http://localhost:51820/api/admin/media \
     -H "Authorization: Bearer $TOKEN" \
     -F "files=@/tmp/p6a.png" | jq .
```

Expected: `{"ok":[{"id":N,"filename":"p6a.png","url":"/media/<bucket>/<uuid>-p6a.png", ...}], "failed":[]}`.

- [ ] **Step 4: Manual smoke — verify public URL**

Take the `url` from the response and open it:

```bash
curl -sI http://localhost:51820/media/<bucket>/<uuid>-p6a.png
```

Expected: `HTTP/1.1 200 OK` with `content-type: image/png`. A nonexistent path returns 404.

- [ ] **Step 5: Manual smoke — verify FK SET NULL**

```bash
docker exec backend-postgres-1 psql -U myblog -d myblog -c \
  "UPDATE site_meta SET avatar_id = (SELECT MAX(id) FROM media) WHERE id = 1; \
   SELECT id, avatar_id FROM site_meta;"
```

Then DELETE the media row:

```bash
curl -s -X DELETE http://localhost:51820/api/admin/media/<id> \
     -H "Authorization: Bearer $TOKEN"
docker exec backend-postgres-1 psql -U myblog -d myblog -c \
  "SELECT id, avatar_id FROM site_meta;"
```

Expected: `avatar_id` becomes NULL automatically.

- [ ] **Step 6: Commit (if any uncommitted lint / cleanup changes)**

```bash
cd backend && git status
# if clean, no commit needed; otherwise:
# git add . && git commit -m "chore(phase6a): final cleanup"
```

- [ ] **Step 7: Merge note**

Branch will be ready for end-of-phase code review and merge to `main`. Do NOT merge yet — that's the `superpowers:requesting-code-review` step in the calling workflow.

---

## Acceptance Criteria Mapping

| Spec §10.4 criterion | Task |
|---|---|
| `media` table + `site_meta.avatar_id` FK; round-trip clean | 2, 15 |
| All five admin routes return 401 without auth | 11, 12, 13, 14 |
| Batch upload returns split `ok`/`failed` | 14 |
| Pillow canonicalizes MIME on extension/byte mismatch | 6 |
| SVG with `<script>` rejected at upload | 7 |
| Public `/media/<path>` serves files; 404 if missing | 10, 16 (smoke) |
| Deleting media linked as avatar succeeds; avatar_id → NULL | 13 |
| Three event_log types fire | 12 (alt_updated), 13 (deleted), 14 (uploaded) |
| All P3/P4/P5 tests still pass | 16 |
