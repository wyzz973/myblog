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

## Tests

The test suite **wipes site data** (`test_admin_danger`, `test_site_wiper`, …)
so it must run against a separate database. The session-scoped guard in
`tests/conftest.py` refuses to start unless the DB name contains `test`.

    bash scripts/bootstrap-test-db.sh        # creates myblog_test, runs migrations + seed
    set -a; source .env.test; set +a
    uv run pytest -q

Override (CI / fresh containers only — bypasses the safety check):

    MYBLOG_ALLOW_NON_TEST_DB=1 uv run pytest -q
