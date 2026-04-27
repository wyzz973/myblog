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
