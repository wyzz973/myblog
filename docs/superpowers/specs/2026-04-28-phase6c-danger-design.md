# Phase 6c — Danger Zone Design Spec

> **Phase 6 carve-up**: P6 split into three sub-projects. P6a (Media) merged 2026-04-28. P6b (Analytics) merged 2026-04-28. This is **P6c (Danger zone)** — the final P6 sub-project.

## 1. Goal

Two admin-only catastrophic operations:

- **Export**: produce a self-contained zip backup of the entire site (posts as `.md` with frontmatter + `tables.json` for everything else + `media/` binary payload). Async via ARQ; admin polls for completion and downloads.
- **Delete-site**: schedule a 7-day grace period during which the admin can cancel; on expiry an ARQ task wipes content tables, resets `site_meta` to CLI seed defaults, and **keeps the admin login** so the user is never locked out.

Both operations require password re-authentication. Delete-site additionally requires typing the site `handle` literally. Rate-limited 1/hour/IP.

Import is **out of scope** for this phase (planned later; same export format will be the input format).

## 2. Out of scope

- **Import** — restoring from an exported zip.
- **Multi-tenant export** — single-user blog only.
- **pg_dump format** — exports use a portable JSON+md+binary mix; no Postgres-version coupling.
- **Per-table partial wipe** — delete-site is all-or-nothing; granular admin "delete just comments" is content-router work, not danger zone.
- **Streaming exports** — exports always go through ARQ + filesystem; no synchronous zip stream from a request handler.
- **Encryption / signing of export zips** — out of scope; users can encrypt manually post-download if they care.
- **Webhooks on deletion** — the spec mentions webhooks elsewhere; danger zone doesn't fire any.
- **Admin password change after delete-site wipe** — admin keeps the same credentials; user can reset via existing account flow if they want.

## 3. Data model

### 3.1 New table: `export_jobs`

```sql
CREATE TABLE export_jobs (
    id              VARCHAR(36) PRIMARY KEY,         -- UUID4 string
    status          VARCHAR(16) NOT NULL,            -- pending | running | done | failed
    requested_by    VARCHAR(128) NOT NULL,           -- admin email
    file_size       BIGINT,                          -- bytes when done; NULL otherwise
    error           TEXT,                            -- exception summary when failed
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ                      -- NULL until done/failed
);
CREATE INDEX ix_export_jobs_created_at ON export_jobs (created_at DESC);
```

Status transitions are monotonic and enforced in service code (no SQL CHECK):
`pending → running → done | failed`. Once terminal, no further mutation.

### 3.2 Modify `site_meta`

```sql
ALTER TABLE site_meta ADD COLUMN pending_delete_at TIMESTAMPTZ NULL;
```

NULL means no deletion scheduled. Non-NULL means destruction will fire on or after this UTC timestamp.

### 3.3 Migration `0007_danger`

Forward + reversible. Creates `export_jobs` + index, adds `pending_delete_at` to `site_meta`. Downgrade drops the column then the table + index.

### 3.4 ORM models

- `app/models/export_job.py` — `ExportJob`
- `app/models/site_meta.py` — add `pending_delete_at: Mapped[datetime | None]`

## 4. Export bundle format

### 4.1 Layout inside `data/exports/<job_id>.zip`

```
manifest.json
tables.json
posts/<slug>.md
posts/<slug2>.md
...
media/<bucket>/<uuid>-<filename>
media/<bucket>/<uuid2>-<filename>
...
```

### 4.2 `manifest.json`

```json
{
  "exporter": "p6c",
  "format_version": 1,
  "exported_at": "2026-04-28T15:23:01Z",
  "table_counts": {
    "posts": 21,
    "comments": 14,
    "tags": 5,
    "projects": 3,
    "contacts": 2,
    "now_entries": 4,
    "site_meta": 1,
    "integrations": 2,
    "media": 18,
    "like_events": 67,
    "hit_daily": 312,
    "accounts": 1,
    "contrib_days": 365
  },
  "post_count": 21,
  "media_count": 18,
  "site_handle": "wangyang"
}
```

### 4.3 `posts/<slug>.md`

YAML frontmatter + raw `body_md`. The frontmatter mirrors the row fields (excluding `body_md` itself):

```markdown
---
id: howdy-world
n: "1"
title: Howdy, World
subtitle: a first post
tag: general              # resolved from tag_id → tags.slug
date: 2026-04-01
read: "5"
lang: en
summary: ...
tldr: ...
status: published
featured: false
private: false
comments_enabled: true
created_at: 2026-04-01T00:00:00Z
updated_at: 2026-04-01T00:00:00Z
---
# This is the body...

actual markdown content
```

`tag` is the resolved slug (joined via `posts.tag_id → tags.id → tags.slug`) so the export survives a tag id-renumber. Re-import resolves slug → id.

### 4.4 `tables.json`

A single object, one key per table. Each value is a list of row objects (column name → value). Datetimes ISO-formatted UTC. JSONB columns kept as JSON.

**Tables included**:

- `tags`, `projects`, `contacts`, `now_entries`, `comments`, `site_meta`, `integrations`, `media`, `like_events`, `hit_daily`, `accounts`, `contrib_days`

**`accounts` includes `password_hash` + `tfa_secret_encrypted` + `tfa_enabled`** — required for future-import to preserve auth state. The export is therefore a credential-bearing artifact; password gating + admin-only download enforces this.

**Tables explicitly excluded**:

- `hit_events` (raw, only 30 days; the rolled-up `hit_daily` is what survives)
- `event_log` (admin-noise audit trail; not data)
- `event_log_archive` (P7 future, doesn't exist yet)
- `export_jobs` (recursive; the job that's running would record itself)
- `posts` (already serialized as `.md` files in `posts/`)
- `magic_links`, `api_tokens`, `tfa_recovery_codes` (auth-flow ephemera; will regenerate on demand)

### 4.5 `media/` directory

Walk `data/media/` recursively. Each file is added to the zip preserving its `storage_path` (so `data/media/7f/<uuid>-cat.png` → `media/7f/<uuid>-cat.png` inside the zip). The `media` table in `tables.json` holds metadata; binaries here.

## 5. Service layer

### 5.1 `app/services/danger.py`

```python
class DangerError(Exception): ...

async def verify_password_or_raise(s, *, admin: Account, password: str) -> None:
    """argon2 verify against admin.password_hash. Raise DangerError on mismatch.
    DangerError → router catches → returns 401 with body {'detail': 'invalid credentials'}."""

async def request_export(s, *, admin: Account) -> ExportJob:
    """Generate UUID, INSERT export_jobs(pending) row, enqueue ARQ build_export_task,
    flush. Caller commits."""

async def get_export(s, *, job_id: str) -> ExportJob | None
async def list_exports(s, *, limit: int = 20) -> list[ExportJob]

async def schedule_site_deletion(s, *, days: int = 7) -> datetime:
    """If pending_delete_at already set → raise DangerError('already scheduled').
    Else SET pending_delete_at = NOW() + days. Returns the new timestamp.
    Caller commits."""

async def cancel_site_deletion(s) -> None:
    """SET pending_delete_at = NULL. Caller commits. No-op if already NULL."""

async def get_danger_status(s) -> DangerStatusResponse:
    """{pending_delete_at: datetime|None, days_remaining: int|None}."""
```

### 5.2 `app/services/export_builder.py`

```python
async def build_export_zip(job_id: str) -> tuple[Path, int]:
    """
    Produces data/exports/<job_id>.zip. Returns (path, file_size_bytes).
    Workflow:
      1. Open zip in ZIP_DEFLATED mode.
      2. Stream all DB tables in their own session (read-only). Write tables.json
         and posts/<slug>.md while iterating.
      3. Walk data/media/ recursively, preserving storage_path under media/.
      4. Write manifest.json LAST so its table_counts are accurate.
      5. Close zip; stat size; return path.
    Raises propagated to caller (build_export_task wraps and writes error).
    """
```

Atomic write: use `data/exports/<job_id>.zip.tmp` then rename on completion (cleanup on exception via try/finally).

### 5.3 `app/services/site_wiper.py`

```python
async def wipe_site_content(s) -> dict:
    """TRUNCATE content tables in FK-safe order. Reset site_meta to defaults
    matching CLI seed values. Returns {tables_wiped: int, rows_destroyed_total: int}.

    Wiped: posts, comments, tags, projects, contacts, now_entries, contrib_days,
           like_events, hit_events, hit_daily, integrations, media (DB rows + files in
           data/media/).

    Reset to defaults: site_meta single row replaced with the CLI seed values
    (handle='wangyang', name='汪洋', etc., pending_delete_at=NULL, avatar_id=NULL).

    Preserved: accounts (admin login), api_tokens, magic_links, tfa_recovery_codes,
               export_jobs, event_log, event_log_archive (when it exists).
    """
```

`media` files on disk: walk `data/media/` and unlink each file (idempotent — missing is OK). Then DELETE FROM media. Order: file deletes first, DB delete second (so DB row never points to a still-present orphan).

## 6. ARQ tasks

### 6.1 `app/workers/tasks/danger.py`

```python
async def build_export_task(ctx: dict, job_id: str) -> dict:
    """Drive a single export job. UPDATE pending → running, build zip, UPDATE done
    or failed, write event_log. Re-raises on failure so ARQ marks the job failed."""

async def check_pending_site_deletion(ctx: dict) -> dict:
    """Hourly cron. If site_meta.pending_delete_at <= NOW(): wipe + reset + clear
    the timestamp + write event_log + commit. Returns {checked: int, fired: int}."""

async def prune_old_exports(ctx: dict) -> dict:
    """Daily 03:30 UTC. Walk data/exports/ and delete *.zip with mtime > 7 days ago.
    Then DELETE FROM export_jobs WHERE created_at < NOW() - INTERVAL '7 days'.
    Returns {files_deleted, rows_deleted}."""
```

### 6.2 Cron registration in `app/workers/runner.py`

```python
q.register("build_export_task", t.build_export_task)
q.register("check_pending_site_deletion", t.check_pending_site_deletion)
q.register("prune_old_exports", t.prune_old_exports)

# WorkerSettings.functions += [
#     t.build_export_task,
#     t.check_pending_site_deletion,
#     t.prune_old_exports,
# ]

# WorkerSettings.cron_jobs += [
#     cron(t.check_pending_site_deletion, minute={0}),         # hourly :00
#     cron(t.prune_old_exports, hour={3}, minute={30}),        # daily 03:30 UTC
# ]
```

03:30 chosen to avoid colliding with 03:00 `prune_event_log` + `analytics_rollup`.

### 6.3 conftest registration

`tests/conftest.py` `_register_arq_tasks` fixture must also register the three new tasks for inline-mode tests.

## 7. HTTP API

`app/routers/admin/danger.py`. All endpoints require `current_admin` + `require_scope("write")` for mutations + IP-bucket rate-limit `1/hour` keyed on `f"rl:danger:{client_ip}"` (using existing `app.services.rate_limit.hit`).

### 7.1 `POST /api/admin/danger/export`

Body:
```json
{"password": "..."}
```

Flow: verify password → `request_export` → return `{job_id, status: "pending"}`.

Errors:
- 401 wrong password (and bearer-missing)
- 429 rate-limited

### 7.2 `GET /api/admin/danger/export/{job_id}`

Returns single `ExportJobItem`. 404 if not found.

### 7.3 `GET /api/admin/danger/exports`

Returns `list[ExportJobItem]`, ordered by `created_at DESC`, `limit=20`.

### 7.4 `GET /api/admin/danger/export/{job_id}/download`

Returns `FileResponse` with the zip bytes. Headers:
- `Content-Type: application/zip`
- `Content-Disposition: attachment; filename="myblog-export-<job_id>.zip"`

Path safety: `(data_dir / "exports" / f"{job_id}.zip").resolve()` must startswith `(data_dir / "exports").resolve()`. Otherwise 404 (don't reveal traversal attempt).

Errors:
- 404 if job_id not found OR status != "done" OR file missing on disk

### 7.5 `POST /api/admin/danger/delete-site`

Body:
```json
{"password": "...", "handle": "wangyang"}
```

Flow: verify password → verify `handle == site_meta.handle` (case-sensitive literal) → `schedule_site_deletion` → return `{scheduled_at, days_remaining: 7}`.

Errors:
- 401 wrong password
- 422 wrong handle (Pydantic + manual check)
- 423 Locked when `pending_delete_at` already set (prevents accumulating extensions)
- 429 rate-limited

### 7.6 `POST /api/admin/danger/delete-site/cancel`

No body required (bearer-only). Sets `pending_delete_at = NULL`. Returns 204.

If already NULL → 204 (idempotent).

### 7.7 `GET /api/admin/danger/status`

Returns `DangerStatusResponse`:
```json
{"pending_delete_at": "2026-05-05T00:00:00Z", "days_remaining": 7}
```
or:
```json
{"pending_delete_at": null, "days_remaining": null}
```

Used by admin dashboard to display a banner.

## 8. Pydantic schemas

`app/schemas/danger.py`:

```python
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

## 9. Event log

Six new event types:

- `danger.export_requested` — actor=admin email, target=job_id, meta={}
- `danger.export_completed` — actor=system, target=job_id, meta={file_size}
- `danger.export_failed` — actor=system, target=job_id, meta={error}
- `danger.delete_scheduled` — actor=admin email, meta={scheduled_at}
- `danger.delete_canceled` — actor=admin email, meta={}
- `danger.site_wiped` — actor=system, meta={tables_wiped, rows_destroyed_total}

Wipe **does not** delete `event_log` itself, so the audit trail of past actions survives.

## 10. Test plan

### 10.1 Unit — `tests/test_export_builder.py` (~6 tests)

- `build_export_zip` produces zip containing `manifest.json`, `tables.json`, `posts/<slug>.md`, `media/<storage_path>` for a seeded fixture.
- Empty DB → zip still has manifest + empty `tables.json` (`{"tags":[], "comments":[], ...}`) + no `posts/` + no `media/`.
- post frontmatter is correct YAML with `tag: <slug>` resolved.
- `accounts` written into tables.json with `password_hash`, `tfa_secret_encrypted`, `tfa_enabled`.
- Excluded tables not in tables.json: `hit_events`, `event_log`, `export_jobs`, `posts` (which goes elsewhere).
- Media binary preserved byte-equal: write a known PNG, run export, read back from zip → bytes match.

### 10.2 Unit — `tests/test_site_wiper.py` (~5 tests)

- After wipe: posts/comments/projects/tags/media/now_entries/like_events/hit_events/hit_daily/integrations/contacts/contrib_days all 0 rows.
- After wipe: `accounts` row preserved (admin can still log in via existing `client.post('/api/admin/auth/login', ...)`).
- After wipe: `site_meta` reset to CLI seed defaults — handle="wangyang", name="汪洋", launched_at=date(2026,1,1), `pending_delete_at` is NULL, `avatar_id` is NULL.
- After wipe: `event_log` row count not zero (audit trail survives).
- After wipe: media files on disk are removed under `data/media/` (test seeds a media file then asserts gone).

### 10.3 ARQ tasks — `tests/test_danger_tasks.py` (~6 tests, inline mode)

- `build_export_task(job_id)` happy path: status=done, file_size > 0, zip exists at `data/exports/<id>.zip`.
- `build_export_task` failure path: monkeypatch `build_export_zip` to raise → status=failed, error column populated, no orphan zip.
- `check_pending_site_deletion` no scheduled deletion → returns `{checked: 1, fired: 0}`, no wipe.
- `check_pending_site_deletion` scheduled in past → fires wipe, clears pending_delete_at, writes event.
- `prune_old_exports` removes `*.zip` mtime > 7d + corresponding row; preserves < 7d.
- `prune_old_exports` no-op when nothing old.

### 10.4 HTTP — `tests/test_admin_danger.py` (~14 tests)

- All 7 routes return 401 without bearer.
- `POST /danger/export` wrong password → 401, no DB row inserted, no enqueue.
- `POST /danger/export` correct password → 200 + `{job_id}`, ARQ inline runs to completion, GET `/danger/export/{id}` shows status=done.
- `GET /danger/exports` history sorted by created_at DESC, limit 20.
- `GET /danger/export/{id}/download` status=done → 200 + `application/zip` body.
- `GET /danger/export/{id}/download` status=pending → 404.
- `GET /danger/export/{id}/download` non-existent id → 404.
- `GET /danger/export/{id}/download` path-traversal `..%2F..%2Fetc%2Fpasswd` → 404.
- `POST /danger/delete-site` wrong password → 401, pending_delete_at unchanged.
- `POST /danger/delete-site` correct password + wrong handle → 422.
- `POST /danger/delete-site` correct → 200 + pending_delete_at set + event_log row.
- `POST /danger/delete-site` already scheduled → 423 Locked.
- `POST /danger/delete-site/cancel` → 204 + pending_delete_at NULL.
- `GET /danger/status` reflects current state (both null and set).
- Rate-limit: 2nd POST to any `/danger/*` within an hour → 429.

### 10.5 Migration — `tests/test_alembic_0007_roundtrip.py`

Round-trip 0006 ↔ 0007. Step-explicit pattern from P6a/P6b.

### 10.6 Acceptance criteria

- [ ] `export_jobs` table + `site_meta.pending_delete_at` column created via 0007; round-trip clean.
- [ ] `POST /danger/export` requires password; produces a downloadable zip via ARQ.
- [ ] Export zip layout matches §4 (manifest + tables.json + posts/ + media/).
- [ ] `POST /danger/delete-site` requires password AND handle literal match.
- [ ] `pending_delete_at` reads back via `GET /danger/status`.
- [ ] `ARQ check_pending_site_deletion` triggers wipe at the right time.
- [ ] `wipe_site_content` clears content but preserves accounts + event_log.
- [ ] `prune_old_exports` cleans aged zips + rows.
- [ ] All 6 event_log types fire on the corresponding actions.
- [ ] All P3/P4/P5/P6a/P6b tests still pass (346 baseline + ~31 new ≈ 377).

## 11. Implementation order

`writing-plans` authors detailed TDD steps. High-level:

1. Migration 0007 + ORM models.
2. Pydantic schemas.
3. `danger` service (verify_password, request_export, schedule, cancel, status).
4. `export_builder` service (zip layout, manifest, tables.json, posts md, media walk).
5. `site_wiper` service (wipe + reset + media file cleanup).
6. ARQ tasks (build_export, check_pending, prune_old) + cron registration + conftest.
7. Admin router (7 endpoints).
8. Event_log wiring.
9. Migration round-trip test.
10. Manual smoke (curl-driven export + download + delete-site + cancel).

## 12. Backwards-compat

- `posts` / `tags` / `media` schemas untouched.
- ORM `ExportJob` registered in `app/models/__init__.py`.
- `event_log` gets six new types.
- ARQ worker keeps existing tasks; add 3 new (1 task + 2 cron).
- 0 P3/P4/P5/P6a/P6b-introduced ruff errors maintained.
