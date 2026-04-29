"""Round-trip alembic to 0007 and back to 0008."""
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


def test_0008_downgrade_then_upgrade_clean():
    down = _alembic("downgrade", "0007_danger")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0007_danger" in cur.stdout

    up = _alembic("upgrade", "0008_event_log_archive")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"

    cur = _alembic("current")
    assert cur.returncode == 0
    assert "0008_event_log_archive" in cur.stdout

    # Restore head so other tests run against the latest schema.
    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
