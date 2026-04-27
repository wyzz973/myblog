# Phase 6a — Media Library (Backend) Design Spec

> **Phase 6 carve-up**: P6 was split into three serial sub-projects to keep each spec/plan small. This is **P6a (Media)**. P6b will be Analytics; P6c will be Danger zone (export + delete-site, depends on P6a media for the export bundle).

## 1. Goal

Implement an admin-only media library:

- Upload, list, alt-edit, and delete image files.
- Files served publicly via FastAPI `StaticFiles` mount.
- Wire `site_meta.avatar_id` foreign key so the existing site config can reference an uploaded avatar.

This is a self-contained, single-server filesystem implementation. The `media_storage` service is a thin adapter so a future S3 swap touches only that one module.

## 2. Out of scope

- Image variants/thumbnails — admin shows the full original. (Add later if needed.)
- Content-hash deduplication — every upload is a new row even if bytes match.
- Soft delete / undo — DELETE is hard delete.
- Total-storage cap — single-user blog; not at risk of filling disk.
- Public list/read API — only admin lists; public site references files by URL, no metadata API.
- Pagination beyond `limit` — keeps parity with P4/P5 routes.
- Object Storage / S3 — abstracted via `media_storage` service so it can be added without router changes.

## 3. Data model

### 3.1 New table: `media`

```sql
CREATE TABLE media (
    id            SERIAL PRIMARY KEY,
    filename      VARCHAR(255) NOT NULL,    -- original name, displayed in UI
    storage_path  VARCHAR(512) NOT NULL,    -- "7f/7f3e1abc-cat.png" relative to data/media/
    mime_type     VARCHAR(64)  NOT NULL,
    size          INTEGER NOT NULL,         -- bytes
    width         INTEGER,                  -- NULL for SVG / non-raster
    height        INTEGER,
    alt           TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX ix_media_created_at ON media (created_at DESC);
```

### 3.2 Modify `site_meta`

Add nullable FK column:

```sql
ALTER TABLE site_meta
    ADD COLUMN avatar_id INTEGER
    REFERENCES media(id) ON DELETE SET NULL;
```

`ON DELETE SET NULL` means deleting an avatar-referenced media row never blocks the admin operation; the public site falls back to its default avatar handling.

### 3.3 ORM models

- `app/models/media.py` — `Media` mapped class (typed `Mapped[...]`).
- `app/models/site_meta.py` — add `avatar_id: Mapped[int | None]` with `ForeignKey("media.id", ondelete="SET NULL")`.

### 3.4 Migration `0005_media`

Forward + reversible. Adds the table, the index, and the `avatar_id` column. Downgrade drops the column first (FK reference) then the table + index.

## 4. Storage layout

Files live under `data/media/{aa}/{uuid}-{original_name}` where `{aa}` is the first two characters of the UUID, used as a dispersion bucket so a single dir never grows past a few thousand entries.

Examples:
```
data/media/7f/7f3e1abc-7c19-4a45-9d22-6e5b0a73a91f-cat.png
data/media/c4/c4ab1def-2233-4455-6677-aabbccddeeff-banner.webp
```

`storage_path` column stores the relative path from `data/media/` (`"7f/7f3e1abc-...-cat.png"`).

Public URL is `/media/{storage_path}`, e.g. `https://wangyang.dev/media/7f/7f3e1abc-...-cat.png`.

## 5. Service layer

### 5.1 `app/services/media_storage.py`

Thin adapter — only place that touches the filesystem.

```python
class MediaError(Exception): ...

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

@dataclass
class SaveResult:
    storage_path: str
    mime_type: str            # canonicalized via Pillow / sniff, not just upload header
    size: int
    width: int | None
    height: int | None

async def save(content: bytes, *, declared_mime: str, original_name: str) -> SaveResult:
    """Validates, writes file, returns metadata. Raises MediaError on bad input."""

async def delete(storage_path: str) -> None:
    """Removes the file. Silent if file already missing — idempotent."""

def url_for(storage_path: str) -> str:
    """Returns "/media/{storage_path}". S3 swap changes only this."""
```

Validation order in `save`:

1. `len(content) > MAX_BYTES` → `MediaError("too large, max 10MB")`.
2. `declared_mime not in ALLOWED_MIME` → `MediaError("unsupported mime: {x}")`.
3. For raster MIMEs (`png/jpeg/webp/gif`): open with Pillow `Image.open(BytesIO(content))`. Failure → `MediaError("not a valid image")`. Read `img.format` and remap to canonical MIME — this defeats `.png` extension + JPEG bytes spoofing.
4. For SVG: parse XML (`xml.etree.ElementTree`); reject any `<script>` element or attribute starting with `on` (basic XSS guard). Failure → `MediaError("svg with script content not allowed")`.
5. Generate UUID, compute bucket prefix (`uuid[:2]`), build `storage_path`, write file atomically (write to `.tmp` then rename).
6. Return `SaveResult` with canonical MIME + dims (width/height = None for SVG).

### 5.2 `app/services/media.py`

DB business layer. Service `flush`es; routers `commit` (P4 atomicity invariant).

```python
async def list_all(s, *, limit: int = 100) -> list[Media]
async def get(s, *, media_id: int) -> Media | None
async def create(s, *, save_result: SaveResult, original_filename: str, alt: str | None = None) -> Media
async def patch_alt(s, *, media_id: int, alt: str | None) -> Media | None
async def delete_one(s, *, media_id: int) -> tuple[bool, str | None]:
    """Returns (was_deleted, storage_path_to_remove).
    Caller commits the row delete first, THEN unlinks the file —
    so a crash leaves an orphan file (cleanable later) instead of a row pointing at nothing."""
```

Order-of-operations guarantee for upload:

```
save_to_disk → DB insert → commit
                    ↓ on failure ↓
              storage.delete(storage_path)   # cleanup
              raise MediaError
```

## 6. HTTP API

All under `/api/admin/media`, requiring `current_admin` and `require_scope("write")` for mutations.

### 6.1 GET `/api/admin/media`

Returns `list[MediaItem]` ordered by `created_at DESC`, `limit=100` default.

```json
[
  {"id": 12, "filename": "cat.png", "url": "/media/7f/7f3e1abc-cat.png",
   "mime_type": "image/png", "size": 14502, "width": 800, "height": 600,
   "alt": "a small cat", "created_at": "2026-04-27T10:30:00Z"}
]
```

### 6.2 POST `/api/admin/media`

`multipart/form-data` with `files: list[UploadFile]` (one or many).

Per-file path: `await file.read()` → `media_storage.save(...)` → `media.create(...)`. On `MediaError`, append to `failed`; do not abort the others.

Response is **HTTP 200** with split arrays:

```json
{
  "ok":     [{"id": 12, "filename": "cat.png", ...}, {"id": 13, ...}],
  "failed": [{"filename": "huge.png", "error": "too large, max 10MB"}]
}
```

Decision: 200 instead of 207 because 207 is a WebDAV multistatus and FastAPI clients trip on it; the `failed` array signals partial success.

Each successful row writes `media.uploaded` event_log with meta `{id, size, mime}`.

**Atomicity rule** — each file is its own transaction: open a short-lived `AsyncSessionLocal` per file, do `media.create` + `write_event`, commit. If commit fails for a given file, that file's storage is cleaned up (delete from disk) and an entry is appended to `failed`. This ensures partial-batch isolation: N-1 successes are durable even if file N's commit fails.

### 6.3 GET `/api/admin/media/{id}`

Returns single `MediaItem` or 404.

### 6.4 PATCH `/api/admin/media/{id}`

Body: `{"alt": "..." | null}` — only field that can be edited post-upload.

Writes `media.alt_updated` event with meta `{id, old, new}`. 404 if not found.

### 6.5 DELETE `/api/admin/media/{id}`

1. `media.delete_one` → returns `(was_deleted, storage_path)`.
2. `write_event("media.deleted", target=str(id), meta={"filename": ..., "storage_path": ...})`.
3. `await s.commit()` — DB row gone, FK SET NULL fires for any referencing avatar_id.
4. After commit, `await media_storage.delete(storage_path)` — file removed (idempotent).

204 on success, 404 if not found.

## 7. Public serving

`app/main.py`:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/media", StaticFiles(directory=settings.data_dir / "media", check_dir=False))
```

`check_dir=False` so dev startup doesn't fail when the directory hasn't been created yet (first uploads create it). StaticFiles never lists directories; nonexistent paths return 404.

## 8. Pydantic schemas

`app/schemas/media.py`:

```python
class MediaItem(BaseModel):
    id: int
    filename: str
    url: str
    mime_type: str
    size: int
    width: int | None
    height: int | None
    alt: str | None
    created_at: datetime

class MediaPatch(BaseModel):
    alt: str | None = None

class MediaUploadResponse(BaseModel):
    ok: list[MediaItem]
    failed: list[MediaUploadFailure]

class MediaUploadFailure(BaseModel):
    filename: str
    error: str
```

## 9. Event log

Three new event types (extend §9 of P5 spec inventory):

- `media.uploaded` — actor=admin email, target=str(id), meta={filename, size, mime, width, height}
- `media.alt_updated` — meta={id, old, new}
- `media.deleted` — meta={id, filename, storage_path}

## 10. Test plan

### 10.1 Unit (`tests/test_media_storage.py`)

- save accepts PNG/JPEG/WEBP/GIF (use Pillow to generate fixture bytes); width/height correct.
- save accepts valid minimal SVG; width/height = None.
- save rejects `application/pdf` declared MIME → `MediaError("unsupported mime")`.
- save rejects > 10 MB content → `MediaError("too large")`.
- save rejects `.png`-claimed bytes that aren't actually decodable → `MediaError("not a valid image")`.
- save **canonicalizes MIME** when extension lies (declared `image/png`, real bytes JPEG → returned `mime_type` is `image/jpeg`).
- save rejects SVG containing `<script>`; rejects SVG with `onload=` attribute.
- delete removes file; second call on already-missing path is a no-op (idempotent).

### 10.2 HTTP (`tests/test_admin_media.py`)

- 401 without bearer on every route (GET / POST / PATCH / DELETE).
- GET empty → `[]`.
- POST single PNG → 200 with `ok=[1]`, `failed=[]`; row stored; file exists.
- POST 3 files (2 valid, 1 oversize) → 200 with `ok=[2]`, `failed=[1]`; 2 rows + 2 files; oversize neither written nor inserted.
- PATCH alt updates field; event_log row written.
- DELETE 204; file gone; row gone.
- DELETE when `site_meta.avatar_id == id` → succeeds; avatar_id is now NULL (FK SET NULL behavior verified).
- GET single 404 for missing id.

### 10.3 Migration (`tests/test_alembic_0005_roundtrip.py`)

Same subprocess pattern as `test_alembic_0004_roundtrip.py`:

```
alembic downgrade 0004_integrations  →  alembic upgrade head  →  alembic current == 0005_media
```

### 10.4 Acceptance criteria

- [ ] `media` table + `site_meta.avatar_id` FK created via 0005_media; round-trip clean.
- [ ] All five admin routes return 401 without auth.
- [ ] Batch upload returns split `ok`/`failed` shape.
- [ ] Pillow canonicalizes MIME on extension/byte mismatch.
- [ ] SVG with `<script>` is rejected at upload time.
- [ ] Public `/media/<path>` serves uploaded files; non-existent → 404.
- [ ] Deleting media linked as avatar succeeds; site_meta.avatar_id becomes NULL.
- [ ] Three new event_log types fire on the corresponding actions.
- [ ] All P3/P4/P5 tests still pass (≥260 baseline + ~18 new = ~278).

## 11. Implementation order

Tasks are authored in detail by `writing-plans` with TDD steps. The high-level order:

1. Pillow dependency added; `0005_media` migration written + applied.
2. ORM models: `Media`; extend `SiteMeta` with `avatar_id`.
3. Pydantic schemas (`MediaItem`, `MediaUploadResponse`, `MediaUploadFailure`, `MediaPatch`).
4. `media_storage` service with validation tests first (TDD).
5. `media` DB service with create/list/get/patch_alt/delete_one.
6. `StaticFiles` mount in `app/main.py`.
7. Admin router with all five endpoints + per-file isolation in POST.
8. Event_log wiring for the three new event types.
9. Alembic round-trip test.
10. Manual smoke: upload via curl, verify public URL, verify avatar FK SET NULL.

## 12. P3 / P4 / P5 backwards-compat

- ORM `Media` registered in `app/models/__init__.py`; downstream importers (analytics-future, danger-export-future) import it through that.
- `site_meta` test fixtures must keep working. The new column is NULL-able with no default so existing rows survive migration.
- No changes to `event_log`, ARQ tasks, integrations, or auth surface.
- 0 P3/P4/P5-introduced ruff errors maintained.
