"""Round-trip alembic to 0003 and back to 0004 to exercise downgrade."""
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


def test_0004_downgrade_then_upgrade_clean():
    # Down to 0003: drops integrations + now_entries + partial unique index.
    down = _alembic("downgrade", "0003_interactions")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"

    # Up to head: re-creates them with JSONB extra_json + partial index.
    up = _alembic("upgrade", "head")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"

    # Verify head is 0004_integrations.
    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0004_integrations" in cur.stdout
