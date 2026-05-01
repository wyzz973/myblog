<div align="center">

# myblog

**A self-hosted personal blogging platform with a batteries-included admin console.**

FastAPI · Postgres · Redis · React · Vite

</div>

---

## Overview

`myblog` is an opinionated, single-tenant publishing platform for people who
want a personal site they actually own — content, comments, analytics, and
all. It pairs a typed Python backend with a hand-built React admin console,
and ships with the moving parts a real site needs: a markdown post engine,
an author-managed media library, cookie-less analytics, comment moderation,
GitHub contribution sync, and a portable export format you can walk away
with.

The codebase is intentionally small. Two halves, ~27k lines total, no
plugin runtime, no theme abstraction layer — just the surface area you'd
sketch on a whiteboard if you were starting from scratch.

## Features

- **Markdown-first writing** — frontmatter + body, live preview, scheduled
  publishing, draft / published / scheduled status, per-post tags
- **Media library** — drag-and-drop multi-upload, alt-text editing, thumbnail
  grid, reusable across posts and the author profile
- **Comment moderation** — pending / approved / spam queue with inline admin
  replies, per-post threading, email-hash storage (no plaintext PII)
- **Cookie-less analytics** — beacon-driven hit logging with 60s dedup, daily
  rollups for top paths / referrers / countries / posts / tags
- **Authentication** — argon2id passwords, JWT bearer + refresh cookie,
  optional TOTP 2FA with recovery codes, magic-link login, scoped API tokens
- **GitHub integration** — auto-syncs your contribution graph and owned
  public repos into the projects section
- **Portable data** — one click exports the entire site (DB + media) as a
  versioned zip; another imports it back into a fresh instance
- **Self-hosted by default** — single Postgres, single Redis, one Python
  process for the API, one for the worker, one Vite bundle on the edge

## Tech stack

**Backend** — FastAPI 0.115, async SQLAlchemy 2.0, Pydantic v2, Alembic,
asyncpg, ARQ workers, structlog, argon2-cffi, PyJWT, mistune, Pillow.

**Frontend** — Vite 5, React 18 (plain JavaScript, no TypeScript), React
Router 6, inline-style design tokens, no CSS framework.

**Infrastructure** — Postgres 16, Redis 7. Docker Compose for local dev.

## Quick start

You'll need **Docker**, **Python 3.12+** with [`uv`](https://docs.astral.sh/uv/),
and **Node 18+**.

```bash
# 1. infrastructure
cd backend
docker compose -f docker-compose.dev.yml up -d

# 2. backend
cp .env.example .env                # fill JWT_SECRET, SECRETS_KEY, LIKE_SALT
uv sync
uv run alembic upgrade head
uv run python -m app.cli seed admin --email admin@example.com --password changeme
uv run python -m app.cli seed bootstrap
uv run uvicorn app.main:app --reload --port 51820

# 3. background worker (separate shell)
uv run arq app.workers.runner.WorkerSettings

# 4. frontend (from repo root)
npm install
npm run dev
```

Open the public site at <http://localhost:5173/> and the admin console at
<http://localhost:5173/admin>. The Vite dev server proxies `/api` and
`/media` to the backend, so there's no CORS configuration to worry about.

## Project layout

```
.
├── backend/
│   ├── app/
│   │   ├── routers/         # public (read-only) + admin (mutating, JWT)
│   │   ├── models/          # SQLAlchemy Mapped[…] declarative models
│   │   ├── services/        # business logic, framework-free
│   │   ├── schemas/         # Pydantic boundary contracts
│   │   ├── workers/         # ARQ task modules + worker entrypoint
│   │   └── cli.py           # typer CLI: bootstrap, seed admin
│   ├── alembic/versions/    # numbered migrations
│   └── tests/
├── src/
│   ├── admin/               # admin console screens + auth shell
│   ├── components/          # public site primitives
│   ├── api/                 # one fetch client per domain
│   ├── pages/               # post reader, project pages
│   └── App.jsx, main.jsx    # public site entry
└── docs/
```

## License

MIT. See `LICENSE` for the full text.
