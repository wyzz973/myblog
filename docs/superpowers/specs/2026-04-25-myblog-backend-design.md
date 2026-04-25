# wangyang.dev — Backend Design

| | |
|---|---|
| **Date** | 2026-04-25 |
| **Status** | Draft, pending user review |
| **Author** | Claude (under @sd3 direction) |
| **Stakeholder** | @sd3 — sole admin |
| **Scope** | Backend for an existing Vite + React personal blog, plus its admin console |

This document is the output of a brainstorming session. It is the source of truth for the backend implementation that follows; an implementation plan will be written from it next.

---

## 1. Context

The frontend (`/Users/sd3/Desktop/project/MyBlog/`) is a Vite + React app that today reads its data from a static `src/data.js` module (posts, projects, tags, contribution grid, site metadata). All state that crosses sessions is fake: likes are a randomised localStorage counter, the contribution grid is a deterministic LCG, the search filters in-memory.

A second prototype, exported from claude.ai/design, lays out a 13-screen admin console (dashboard, analytics, posts, media, comments, tags, site, profile, contacts, projects, now, pet, settings). The user has chosen to implement **everything** the admin prototype shows, with two carve-outs that conflict with the prototype:

- Database stays Postgres (per admin status bar) — **upgraded from the previous SQLite decision**.
- Frontend keeps **Terminal layout only**. Editorial (B) and Dashboard (C) are not restored. The admin "default homepage layout" tile picker is dropped.

The backend must:

1. Serve the existing frontend's data needs (posts, tags, projects, contributions, site metadata, real likes).
2. Power the admin console (CRUD for every editable entity, comments moderation, media library, analytics, integrations, etc.).
3. Stay deployable on a single small VPS (the user's existing target).

## 2. Architecture overview

```
┌──────────────────┐  HTTP/JSON   ┌──────────────────────────────┐
│  Vite + React    │ ─────────►   │  FastAPI (uvicorn)           │
│  :51730 (dev)    │  CORS allowed│  :51820                      │
│  /api/* fetch    │ ◄─────────── │                              │
└──────────────────┘              │  + ARQ worker (Redis-backed) │
                                  └──────────────┬───────────────┘
                                                 │
                ┌────────────────────────────────┼─────────────────────────────────┐
                ▼                                ▼                                 ▼
         Postgres 16                       Redis 7                          ./data/
         (primary store)              (cache, queue, rate limit)         media/, exports/
                                                                          ./posts/
                                                                          (markdown source)
```

- **Public origin** stays at `:51730`, **API origin** at `:51820`. CORS allows the public origin only. Webhooks (`/webhooks/*`) bypass CORS.
- **Posts** are markdown files under `backend/posts/`, mirrored into Postgres on import. Markdown is the source of truth; `posts.body_json` is a render cache.
- **Media** files live under `backend/data/media/` initially. The `media_storage` service is an adapter so we can swap to S3-compatible storage without router changes.
- **Sessions** are JWT (access) + httpOnly refresh cookie. Refresh tokens are persisted in Redis with TTL, allowing single-click revocation without DB writes on every request.
- **Background work** runs in a separate ARQ worker process (scheduled posts, GitHub sync, email, analytics rollups). One uvicorn + one ARQ worker is the dev process model.

## 3. Data model

15 tables. SQLAlchemy 2.0 async ORM. Alembic migrations. Postgres 16.

### 3.1 Content tables

| Table | Purpose | Notable columns |
|---|---|---|
| `posts` | Articles | `id`(slug PK), `n`, `title`, `subtitle`, `tag_id`(FK→tags.id), `date`, `read`, `lang`, `summary`, `tldr`, `body_md`(text, source of truth), `body_json`(jsonb, render cache), `word_count`, `status`(draft/published/scheduled), `scheduled_at`, `featured`, `private`, `comments_enabled`, `created_at`, `updated_at`. Indexed on `(status, date desc)`, `(tag_id, status, date desc)`. **API surface uses tag slug**, not `tag_id`; the router resolves slug↔id |
| `tags` | Tag taxonomy | `id`(PK), `slug`(unique), `name`, `color`, `sort_order`. UI-managed; no longer derived |
| `projects` | Open-source / side projects | `name`(PK), `description`, `lang`, `stars`, `status`(active/maintained/archived), `sort_order`, `visible` |
| `contacts` | Contact channels | `id`(PK), `label`, `value`, `href`, `visible`, `sort_order` |
| `now_entries` | "What I'm doing now" history | `id`(PK), `body_md`, `listening`, `reading`, `created_at`, `is_current`(bool, only one true at a time) |
| `media` | Uploaded files | `id`(PK), `filename`, `mime_type`, `size`, `width`, `height`, `alt`, `created_at` |

### 3.2 Engagement tables

| Table | Purpose |
|---|---|
| `like_events` | `(post_id, ip_hash, day)` UNIQUE; idempotent per-IP-per-day |
| `comments` | `id`, `post_id`(FK), `who`, `email_hash`, `body`(**plaintext only, not markdown**), `status`(pending/approved/spam), `flag`, `parent_id`(self-FK, for replies), `created_at`. `email_hash = sha256(email + LIKE_SALT)` for moderation hints without storing raw email |
| `hit_events` | Raw analytics events: `id`, `path`, `referrer`, `country`, `created_at`. Aggregated nightly into `hit_daily` |
| `hit_daily` | Aggregated daily counts: `(date, path)` PK, `hits`, `referrers_top` JSON, `countries_top` JSON |

### 3.3 System tables

| Table | Purpose |
|---|---|
| `accounts` | Admin user table. `id`, `email`, `password_hash`(argon2id), `tfa_secret_encrypted`, `tfa_enabled`, `magic_link_enabled`, `created_at`. Single row in MVP |
| `magic_links` | `token_hash`(sha256), `account_id`(FK), `expires_at`, `consumed_at` |
| `api_tokens` | Tokens for external apps to call the blog API. `id`, `name`, `scope`, `token_hash`(bcrypt), `last_used_at`, `revoked_at`. Raw token only shown once on creation |
| `integrations` | Encrypted third-party credentials. `name`(PK in {github,vercel,plausible,anthropic}), `username`, `secret_encrypted`(Fernet), `extra_json`, `last_synced_at`, `last_status` |
| `contrib_days` | GitHub contributions, daily granularity. `day`(PK), `level`(0..4), `count`. Aggregated to 52×7 grid by the contrib router |
| `event_log` | Audit + activity stream. `id`, `type`(eg `post.created`), `actor`, `target`, `meta_json`, `created_at`. Indexed on `(created_at desc)`, `(type, created_at desc)` |
| `event_log_archive` | Same shape as `event_log`. Rows older than 90 days move here nightly; older than 1 year are dropped |
| `site_meta` | Single-row config table (`id` PK, exactly one row). Columns: `handle`, `name`, `name_en`, `role`, `tagline`, `bio`, `location`, `email`, `github`, `pronouns`, `avatar_id`(FK→media), `typing_line`, `stack_chips`(jsonb array), `footer_note`, `default_theme`, `accent_color`, `accent2_color`, `violet_color`, `danger_color`, `launched_at`(for uptime), `pet_config`(jsonb). The "single row" pattern is enforced by a CHECK constraint on `id=1` |

### 3.4 Conventions

- All timestamps are UTC `timestamptz`.
- All slugs match `^[a-z0-9][a-z0-9-]{1,63}$`.
- IP-derived columns store `sha256(ip + LIKE_SALT)`; raw IP never persists.
- Encrypted columns suffix `_encrypted`; reads go through `services.secrets.decrypt`.
- Soft-delete is **not** used; `DELETE` is real. Audit trail is in `event_log`.

## 4. API contract

All responses `application/json`. Field shapes target zero adaptation in the existing frontend `data.js` consumers.

### 4.1 Public endpoints

| Group | Method | Path | Notes |
|---|---|---|---|
| Site | GET | `/api/site` | Site metadata + theme defaults + uptime |
| Site | GET | `/api/profile` | Hero/identity (typing line, stack chips, avatar URL) |
| Site | GET | `/api/contacts` | Visible contact rows |
| Site | GET | `/api/healthz` | Liveness probe `{ok:true}` |
| Site | GET | `/api/readyz` | Readiness probe (DB + Redis ping); 503 if unready |
| Posts | GET | `/api/posts?tag=&q=&limit=20&offset=0&lang=` | List; filters published+!private |
| Posts | GET | `/api/posts/{id}` | Detail. Includes `likes`, `body[]`, `tldr` |
| Posts | POST | `/api/posts/{id}/like` | Idempotent per (IP, day). Returns `{likes, liked}` |
| Comments | GET | `/api/posts/{id}/comments` | Approved comments only |
| Comments | POST | `/api/posts/{id}/comments` | Submit; defaults to `pending`. Body `{who, email, body}` |
| Tags | GET | `/api/tags` | All tags + post counts (synthetic `id:"all"` synthesised) |
| Projects | GET | `/api/projects` | Visible projects, ordered |
| Now | GET | `/api/now` | Latest `now` entry + most recent N history entries |
| Contrib | GET | `/api/contrib?weeks=52` | Returns `{weeks, grid:[[lvl×7]×52], months, commits, source:"github"\|"seed", synced_at?}` |
| Pet | GET | `/api/pet/config` | Public-safe subset (species, hat, tint, enabled, visitor_can_change) |
| Pet | POST | `/api/pet/summon` | LLM-generated quip; per-IP rate-limited; falls back to canned line on error |
| Track | POST | `/api/track` | Cookie-less hit ping; never returns 429 (silently drops over budget) |

### 4.2 Admin endpoints

All require `Authorization: Bearer <access_token>`; many additionally require an active 2FA-elevated session if 2FA is enabled.

#### Auth & session

| Method | Path | Notes |
|---|---|---|
| POST | `/api/admin/auth/login` | `{email, password}` → `{access, tfa_required, challenge?}` |
| POST | `/api/admin/auth/2fa` | `{challenge, code}` → `{access}` |
| POST | `/api/admin/auth/refresh` | Uses cookie; returns new access |
| POST | `/api/admin/auth/magic-link` | `{email}` → `202`. Rate-limited per email |
| GET | `/api/admin/auth/magic-link/verify?t=` | Single-use; returns `{access}` |
| POST | `/api/admin/auth/logout` | Revokes refresh + jti |
| GET | `/api/admin/session` | Current account + capabilities |

#### Content

| Method | Path | Notes |
|---|---|---|
| GET | `/api/admin/posts?status=&q=&tag=&page=` | Includes drafts/scheduled |
| POST | `/api/admin/posts` | Body JSON `{markdown, status?, scheduled_at?, featured?, private?, comments_enabled?}` **or** multipart with `.md` files (single or many, ≤20). Multi returns 207 |
| GET / PATCH / DELETE | `/api/admin/posts/{id}` | |
| POST | `/api/admin/posts/render-preview` | `{markdown}` → `{frontmatter, body, errors[], warnings[]}` |
| GET / POST / PATCH / DELETE | `/api/admin/tags[/:id]` | |
| PUT | `/api/admin/tags/order` | Body `{ids:[...]}` atomic reorder |
| GET / POST / PATCH / DELETE | `/api/admin/projects[/:id]` | |
| PUT | `/api/admin/projects/order` | |
| GET / POST / PATCH / DELETE | `/api/admin/contacts[/:id]` | |
| PUT | `/api/admin/contacts/order` | |
| GET / POST / PATCH / DELETE | `/api/admin/now[/:id]` | |
| GET / POST / DELETE | `/api/admin/media[/:id]` | multipart upload |

#### Comments backoffice

| Method | Path | Notes |
|---|---|---|
| GET | `/api/admin/comments?status=` | |
| PATCH | `/api/admin/comments/{id}` | Status transitions + reply text |
| DELETE | `/api/admin/comments/{id}` | |

#### Site config

| Method | Path | Notes |
|---|---|---|
| GET / PUT | `/api/admin/profile` | Whole-record replace |
| GET / PUT | `/api/admin/site` | basics; `default_layout` is **not** in this payload |
| GET / PUT | `/api/admin/theme` | accent / accent-2 / violet / danger |
| GET / PUT | `/api/admin/pet` | LLM model, system prompt, fallback lines, rate limit, etc. |

#### Integrations & credentials

| Method | Path | Notes |
|---|---|---|
| GET / PUT | `/api/admin/integrations/github` | `{username, token?}`; PUT pings GraphQL to validate (422 on fail), then triggers full sync |
| POST | `/api/admin/integrations/github/sync` | Manual sync |
| GET / PUT | `/api/admin/integrations/anthropic` | API key + model preference |
| GET / PUT | `/api/admin/integrations/vercel` | Deploy hook URL + secret |
| GET / PUT | `/api/admin/integrations/plausible` | Site id (optional) |
| GET | `/api/admin/integrations/{name}` | Single integration status |
| DELETE | `/api/admin/integrations/{name}` | Disconnect (zeroes encrypted columns) |
| GET / POST / DELETE | `/api/admin/api-tokens[/:id]` | Token raw value shown once on POST |

#### Account

| Method | Path | Notes |
|---|---|---|
| PATCH | `/api/admin/account/email` | Verifies old password |
| PATCH | `/api/admin/account/password` | Verifies old password |
| POST | `/api/admin/account/2fa/setup` | Returns `{secret, otpauth_uri, qr_svg}` |
| POST | `/api/admin/account/2fa/enable` | Verifies first TOTP code |
| DELETE | `/api/admin/account/2fa` | Confirms with current TOTP |
| PATCH | `/api/admin/account/magic-link` | Toggle |

#### Dashboard, analytics, deploy

| Method | Path | Notes |
|---|---|---|
| GET | `/api/admin/dashboard/summary` | Four headline stats |
| GET | `/api/admin/dashboard/activity?limit=` | Recent event_log entries |
| GET | `/api/admin/analytics/visitors?period=30d` | Daily series |
| GET | `/api/admin/analytics/top-posts?period=7d` | |
| GET | `/api/admin/analytics/referrers` | |
| GET | `/api/admin/analytics/countries` | |
| GET | `/api/admin/build/latest` | Last deploy commit/branch/duration/status |
| POST | `/api/admin/build/redeploy` | Triggers configured Vercel deploy hook |
| GET | `/api/admin/activity?type=&limit=` | Full event_log |

#### Danger zone

| Method | Path | Notes |
|---|---|---|
| POST | `/api/admin/danger/export` | Returns zip stream of posts + media + DB dump |
| POST | `/api/admin/danger/import` | Accepts zip; replaces store after second confirm |
| POST | `/api/admin/danger/delete-site` | Starts 7-day grace period |

### 4.3 Webhooks

| Method | Path | Notes |
|---|---|---|
| POST | `/webhooks/vercel/deploy` | HMAC-validated; updates build status + writes event_log |

### 4.4 Cross-cutting conventions

- **Errors** match FastAPI's `{"detail": ...}` shape; rate-limit responses include `retry_after`.
- **Rate limits**: see §6.3.
- **Reorder endpoints** all take `{ids:[...]}` and apply atomically inside a single transaction.
- **Token storage**: third-party secrets encrypted with Fernet (key from env). Raw values never logged or echoed.
- **Activity log**: every admin write hits `services.event_log.write` synchronously (best-effort; failures warn but don't block).
- **Pagination**: `limit ≤ 100`. Default 20. Responses are `{items, total, limit, offset}`.

## 5. Markdown rendering pipeline

### 5.1 Library choice

Real-world fixtures from `/Users/sd3/Desktop/工具文档` show heavy use of multi-level headings, GFM tables, blockquotes, ordered/unordered lists, bold/italic, links, fenced code with language hints, and horizontal rules. A self-rolled tokenizer would silently drop most of this. Use **mistune** (Python, fast, AST-mode) and walk its AST into our node schema below.

Disallowed GFM features (reject with 422):

- Task lists `- [ ]`
- Footnotes `[^id]`
- Strikethrough `~~text~~`
- Inline HTML (`<div>`, `<span>`, …)

### 5.2 Node schema (TypeScript notation)

```ts
type Block =
  | { t: 'h1'|'h2'|'h3'|'h4', c: string, inline: Inline[] }
  | { t: 'p',     c: string, inline: Inline[] }
  | { t: 'code',  c: string, lang?: string }
  | { t: 'ul'|'ol', items: { c: string, inline: Inline[] }[] }
  | { t: 'quote', c: string, inline: Inline[] }
  | { t: 'hr' }
  | { t: 'table', header: string[], align: ('left'|'center'|'right')[], rows: string[][] }
  | { t: 'image', src: string, alt: string };

type Inline =
  | { kind: 'text', s: string }
  | { kind: 'code', s: string }
  | { kind: 'b' | 'i', children: Inline[] }
  | { kind: 'a', href: string, children: Inline[] };
```

`body_json` is an array of `Block`. `c` always carries the plain-text projection so server-side search can scan it without walking `inline`.

### 5.3 Frontmatter

Pydantic-validated YAML at the top of each markdown file:

```yaml
id: termius-utf8                    # slug, unique
n: "042"                             # display number, "001"-"999"
title: Termius 中文乱码解决方案
subtitle: UTF-8 编码配置指南          # optional
tag: devtools                        # must exist in tags table
date: 2026-04-12                     # ISO date
read: 6 min                          # optional, auto-derived if missing
lang: zh                             # zh | en
summary: ...                         # optional, derived from first <p>
tldr: ...                            # optional
status: published                    # draft | published | scheduled
scheduled_at: 2026-04-12T00:00:00Z   # required iff status=scheduled
featured: false
private: false
comments_enabled: true
```

### 5.4 Auto-derived fields

| Field | Derivation |
|---|---|
| `read` | `ceil(word_count / 240)` minutes |
| `word_count` | `len(re.findall(r'\w+', plaintext)) + chinese_char_count` |
| `summary` | First 140 chars of first paragraph |
| `lang` | If user omitted: char-ratio detection (≥30% CJK ⇒ `zh`) |

### 5.5 `.md` upload (single & bulk)

`POST /api/admin/posts` with `Content-Type: multipart/form-data` accepts up to 20 `.md` files. Each is run through the pipeline independently. The response uses HTTP 207 for partial success and shape:

```json
{
  "results": [
    { "file": "post-001.md", "ok": true, "post": { ... } },
    { "file": "post-002.md", "ok": false, "status": 422, "errors": [...] }
  ],
  "summary": { "total": 2, "ok": 1, "failed": 1 }
}
```

Constraints: extension `.md|.markdown`, UTF-8 (BOM allowed), single file ≤ 1 MB. `?overwrite=true` switches conflict from 409 to PATCH.

### 5.6 CLI bulk import

```
python -m app.cli import-md <path>                     # single file
python -m app.cli import-md <dir> [--overwrite]        # recursive
python -m app.cli import-legacy <data.js path>         # bootstrap from old data.js
```

When importing a file with no frontmatter, the CLI auto-infers and prints a dry-run summary; `--yes` is required to commit:

| Inferred | From |
|---|---|
| `id` | filename slug |
| `title` | first H1 |
| `date` | file mtime |
| `lang` | character-ratio detection |
| `n` | one greater than current max |
| `tag` | `--default-tag` flag, or interactive prompt |

**Sensitive-name skip**: filenames matching `^(accounts?|secrets?|passwords?|credentials?|.*\.env)` are reported as `⊘ skipped (sensitive name)` and excluded from both fixture import and pipeline tests.

### 5.7 Round-trip invariance

`render(parse(md)).body_json == parse(md).body_json` must hold. Golden fixtures live under `backend/tests/fixtures/real_md/` (sourced from `/Users/sd3/Desktop/工具文档`, sensitive names excluded) plus the 12 articles reverse-constructed from `data.js`. CI fails if any fixture fails round-trip.

## 6. Auth, secrets, rate limit

### 6.1 Login flow

```
admin → POST /api/admin/auth/login {email, password}
  ├── 2FA disabled  ⇒ {access:JWT, refresh:cookie}
  └── 2FA enabled   ⇒ {tfa_required:true, challenge:jti}
                       admin → POST /api/admin/auth/2fa {challenge, code}
                                 ⇒ {access, refresh:cookie}
```

- Access token: HS256-signed JWT, 15-minute TTL, includes `sub`, `jti`, `iat`, `exp`.
- Refresh: opaque random, 32 bytes, stored in Redis under `refresh:{sub}:{jti}` with 30-day TTL. Cookie is httpOnly, SameSite=Lax, Secure in prod. Rotated on use (old jti invalidated).
- Magic-link: `magic_links` row with `token_hash = sha256(token)`, 15-minute TTL, single-use.

### 6.2 Secret storage

| Data | Algorithm |
|---|---|
| Account password | argon2id (m=64MB, t=3, p=4) via `argon2-cffi` |
| Third-party API keys (GH PAT, Anthropic key, Vercel hook secret) | Fernet symmetric, key from `SECRETS_KEY` env |
| TOTP shared secret | Fernet (same key) |
| Outbound API tokens | bcrypt hash, raw shown once |
| Webhook HMAC secrets | Fernet |

`SECRETS_KEY_PREVIOUS` is supported for grace-period rotation; decrypt tries new key first, then previous.

### 6.3 Rate limits

Implemented as a Redis token-bucket dependency.

| Endpoint | Dimension | Budget |
|---|---|---|
| `/api/admin/auth/login` | IP | 5/min, 10 fails ⇒ 15-min lockout |
| `/api/admin/auth/2fa` | challenge | 5 attempts |
| `/api/admin/auth/magic-link` | email | 3/hour |
| `/api/posts/{id}/like` | IP+post | 10/min |
| `/api/posts/{id}/comments` | IP | 3/min |
| `/api/pet/summon` | IP | 6/min (admin-tunable) |
| `/api/track` | IP | 60/min (silent drop) |
| Generic admin write | session | 60/min |
| `/api/admin/danger/*` | session | 1/hour |

### 6.4 CSRF / CORS

- CORS allows the configured frontend origin only.
- All write endpoints require `Authorization` header — cookie-only requests are rejected. This neutralises CSRF without a token-double-submit.
- Webhooks bypass CORS; HMAC validation is the only gate.

### 6.5 Audit log

`event_log` is written synchronously (best-effort) on every admin write and on auth events. It powers both the dashboard activity feed and `/api/admin/activity`. Retention: 90 days hot, 1 year archived, then dropped.

## 7. Project skeleton

### 7.1 Tree (abridged)

```
backend/
├── pyproject.toml          # uv-managed
├── alembic.ini
├── alembic/versions/
├── docker-compose.dev.yml  # postgres + redis + adminer
├── Dockerfile              # for later deploy
├── .env.example
├── posts/                  # markdown source-of-truth
├── data/{media,exports}/
├── tests/{conftest.py, fixtures/real_md/, test_*.py}
└── app/
    ├── main.py             # FastAPI factory + middleware
    ├── config.py           # pydantic-settings
    ├── deps.py             # db / redis / current_admin / rate_limit
    ├── db.py / redis.py
    ├── models/             # 15 SQLAlchemy models
    ├── schemas/            # Pydantic IO models
    ├── routers/{public,admin,webhooks}/
    ├── services/
    │   ├── markdown_pipeline.py
    │   ├── auth.py
    │   ├── secrets.py
    │   ├── rate_limit.py
    │   ├── github_sync.py
    │   ├── pet_llm.py
    │   ├── analytics.py
    │   ├── media_storage.py
    │   ├── email.py
    │   └── event_log.py
    ├── workers/{runner.py, tasks.py}     # ARQ
    ├── cli.py                            # Typer
    └── utils/
```

### 7.2 Process model

Three terminals during development:

```
uvicorn app.main:app --port 51820 --reload
arq app.workers.runner.WorkerSettings
docker compose -f docker-compose.dev.yml up   # postgres + redis
```

In production, add a Caddy or Nginx reverse proxy in front for TLS + serving the compiled frontend.

### 7.3 Background tasks (ARQ)

| Task | Schedule | Purpose |
|---|---|---|
| `publish_scheduled_posts` | every 1 min | flip `scheduled` ⇒ `published` when time has passed |
| `sync_github_contrib` | every 1 hour | pull GraphQL, refresh `contrib_days` |
| `cleanup_expired_magic_links` | every 30 min | delete consumed/expired |
| `aggregate_analytics_daily` | daily 00:05 UTC | roll `hit_events` into `hit_daily` |
| `prune_event_log` | daily 03:00 UTC | move >90d rows to archive, drop >1y |
| `send_magic_link_email` | on-demand | queued; retry 3× with backoff |
| `send_comment_notification` | on-demand | optional, when admin enables |
| `recompute_post_word_counts` | on-demand | called after import-md |

### 7.4 Configuration

`pydantic-settings` reads `.env`. Required keys: `database_url`, `redis_url`, `secrets_key`, `jwt_secret`, `cors_origins`. Optional: `secrets_key_previous`, `smtp_*`, `vercel_webhook_secret`. Defaults: `api_port=51820`, `access_token_ttl=900`, `refresh_token_ttl=2_592_000`, `data_dir=./data`, `posts_dir=./posts`, `env=dev`.

### 7.5 Migrations

Alembic with autogenerate. Initial migration creates all 15 tables. Test DB isolation via `pytest-postgresql`.

### 7.6 Bootstrap & seed

```bash
uv sync
docker compose -f docker-compose.dev.yml up -d
uv run alembic upgrade head
uv run python -m app.cli seed admin --email hi@wangyang.dev --password 'changeme'
uv run python -m app.cli seed bootstrap
uv run python -m app.cli import-md /Users/sd3/Desktop/工具文档 --default-tag devtools
uv run uvicorn app.main:app --port 51820 --reload
```

`seed bootstrap` populates default site/profile/theme/pet rows, default tag set, and reverse-imports the 12 legacy posts from the old `data.js` for parity.

### 7.7 Dependency floor

```
fastapi>=0.115, uvicorn[standard]>=0.32,
sqlalchemy[asyncio]>=2.0.36, asyncpg>=0.30, alembic>=1.14,
redis>=5.2, arq>=0.26,
pydantic>=2.10, pydantic-settings>=2.6,
mistune>=3, python-frontmatter>=1.1,
argon2-cffi>=23, cryptography>=44, pyjwt>=2.10, pyotp>=2.9,
aiosmtplib>=3.0, httpx>=0.28, anthropic>=0.40,
typer>=0.15, structlog>=24.
```

Dev: `pytest, pytest-asyncio, pytest-postgresql, fakeredis, httpx, freezegun, respx, mypy, ruff`.

## 8. Testing & observability

### 8.1 Test pyramid

| Layer | Count | Tools |
|---|---|---|
| Unit | 60+ | pytest, freezegun |
| Integration | ~40 | + httpx AsyncClient, pytest-postgresql, fakeredis |
| Contract | ~15 | one per router group, asserts JSON shape that frontend consumes |
| E2E smoke | 3 | login → publish → public read; comment lifecycle; like idempotency |

Coverage gates: `services/` ≥ 90%, overall ≥ 80%.

Round-trip invariance test runs every fixture (real_md/ + reverse-constructed legacy posts) on every CI run.

### 8.2 Error handling

Global handlers register for: `HTTPException`, `RequestValidationError` (422), `IntegrityError` (409), `AuthError` (401), `RateLimited` (429 + retry_after), `NotFoundError` (404), `Exception` (500 + request_id + traceback). All responses use the `{"detail": ...}` envelope.

Request ID middleware injects `X-Request-ID` (uuid7), threads it into structlog context, and echoes on 5xx. 4xx is counted but not error-logged. 5xx always traceback-logs.

### 8.3 Observability

| Signal | Implementation |
|---|---|
| Logs | structlog JSON to stdout |
| Liveness | `/api/healthz` |
| Readiness | `/api/readyz` (DB + Redis ping; 503 if down) |
| Request timing | middleware adds `X-Response-Time-Ms` |
| Metrics | Out of MVP scope; `event_log` + admin Analytics suffice |

### 8.4 Performance budget

| Endpoint | p95 |
|---|---|
| `/api/posts` list | < 50 ms |
| `/api/posts/{id}` | < 30 ms |
| `/api/admin/posts/render-preview` | < 30 ms |
| `/api/track` | < 10 ms (Redis stream) |
| `/api/pet/summon` | < 2 s (5 s timeout ⇒ fallback) |

Single-instance memory < 250 MB.

### 8.5 Out of scope

- Multi-user collaboration (admin is one person, forever).
- i18n framework on the public site.
- CDN / external image storage (local first; S3 later via adapter swap).
- WebSocket push (dashboard polls every 5 s).
- Kubernetes / multi-replica deploys.
- Prometheus / OpenTelemetry instrumentation.

## 9. Decisions log

| Q | Decision | Date |
|---|---|---|
| Q1 backend stack | Python + FastAPI | 2026-04-25 |
| Q2 storage | Postgres + Redis (revised from SQLite) | 2026-04-25 |
| Q3 content format | Markdown source of truth → JSON cache | 2026-04-25 |
| Q4 auth & like-dedup | Full account system (email+password+2FA+magic-link) per admin prototype, **revising** earlier "single Bearer token" choice; like dedup remains IP+day | 2026-04-25 |
| Q5 deployment topology | Frontend / backend separate origins, local-first, deploy later | 2026-04-25 |
| Layouts | Terminal only — no B/C; admin's "default homepage layout" picker dropped | 2026-04-25 |
| GitHub config storage | Stored in admin (DB), not `.env`; falls back to seed data when unconfigured | 2026-04-25 |
| Markdown library | mistune (after seeing real fixtures) | 2026-04-25 |
| Test fixtures | `/Users/sd3/Desktop/工具文档` minus sensitive names + 12 legacy posts | 2026-04-25 |
| Admin UI host | Built into the React frontend (per user direction); the FastAPI backend exposes API only | 2026-04-25 |

## 10. Open questions

- Email sender: SMTP vs Resend/Postmark? — defer until email is needed; default to SMTP (`aiosmtplib`).
- Plausible vs self-hosted analytics: implementing self-hosted in MVP; Plausible integration is just a "site id" pass-through.
- Build/deploy state in MVP: showing the latest webhook payload only (no log proxy yet); manual redeploy uses configured deploy hook.
- When does the admin frontend build land? It's part of the React app, but its implementation is gated on this backend's APIs being concrete.
