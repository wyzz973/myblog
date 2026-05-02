#!/usr/bin/env bash
# One-shot deploy: rsync repo + dist to the prod server, run migrations, restart systemd.
#
# Usage:  ./scripts/deploy.sh [--code-only|--frontend-only]
#
# Requires a `.env.deploy` file at the repo root (gitignored) with at least:
#   SERVER=root@<host>
#   SSHPASS=<password>      # optional; omit if using ssh keys
#   DOMAIN=<your.domain>    # used in the success message
# Also requires `sshpass` on PATH if SSHPASS is set.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env.deploy ]]; then
  cat >&2 <<EOF
error: .env.deploy not found at $ROOT/.env.deploy

Create it (gitignored) with:
  SERVER=root@<your-host>
  SSHPASS=<password>      # optional if using ssh key
  DOMAIN=<your.domain>    # for the success message
EOF
  exit 2
fi
set -a; . .env.deploy; set +a

: "${SERVER:?Set SERVER in .env.deploy}"
: "${REMOTE_REPO:=/opt/myblog/repo}"
: "${REMOTE_DIST:=/opt/myblog/dist}"
: "${DOMAIN:=}"

ssh_run() {
  if [[ -n "${SSHPASS:-}" ]]; then
    sshpass -e ssh -o StrictHostKeyChecking=accept-new "$SERVER" "$@"
  else
    ssh -o StrictHostKeyChecking=accept-new "$SERVER" "$@"
  fi
}
rsync_run() {
  if [[ -n "${SSHPASS:-}" ]]; then
    sshpass -e rsync -az --delete -e 'ssh -o StrictHostKeyChecking=accept-new' "$@"
  else
    rsync -az --delete -e 'ssh -o StrictHostKeyChecking=accept-new' "$@"
  fi
}

MODE="${1:-full}"

case "$MODE" in
  --code-only|--frontend-only|full|"") ;;
  *) echo "usage: $0 [--code-only|--frontend-only]" >&2; exit 2 ;;
esac

if [[ "$MODE" != "--frontend-only" ]]; then
  echo "==> rsync code → $SERVER:$REMOTE_REPO"
  rsync_run \
    --exclude='.git/' --exclude='node_modules/' --exclude='dist/' --exclude='myblog/' \
    --exclude='backend/.venv/' --exclude='backend/.pytest_cache/' --exclude='backend/.mypy_cache/' \
    --exclude='backend/.ruff_cache/' --exclude='backend/myblog_backend.egg-info/' \
    --exclude='backend/.env' --exclude='backend/.env.test' \
    --exclude='.env.deploy' \
    --exclude='*.pyc' --exclude='__pycache__/' --exclude='.DS_Store' \
    --exclude='MyBlog-handoff.zip' \
    "./" "$SERVER:$REMOTE_REPO/"
fi

if [[ "$MODE" != "--code-only" ]]; then
  echo "==> npm run build (local)"
  VITE_API_BASE_URL="" npm run build >/dev/null

  echo "==> rsync dist → $SERVER:$REMOTE_DIST"
  rsync_run "./dist/" "$SERVER:$REMOTE_DIST/"
fi

if [[ "$MODE" != "--frontend-only" ]]; then
  echo "==> uv sync + alembic upgrade head"
  ssh_run 'set -e
    cd /opt/myblog/repo/backend
    sudo -u myblog -H bash -lc "cd /opt/myblog/repo/backend && uv sync --no-dev" >/dev/null
    sudo -u myblog -H bash -lc "cd /opt/myblog/repo/backend && set -a && . .env && set +a && .venv/bin/alembic upgrade head"
    chown -R myblog:myblog /opt/myblog/repo
    systemctl restart myblog-api myblog-worker
    sleep 2
    systemctl is-active myblog-api myblog-worker
  '
fi

if [[ -n "$DOMAIN" ]]; then
  echo "✓ deploy complete — https://$DOMAIN"
else
  echo "✓ deploy complete"
fi
