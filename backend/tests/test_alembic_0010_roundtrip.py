"""Round-trip alembic to 0009 and back to 0010."""
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


def test_0010_downgrade_then_upgrade_clean():
    down = _alembic("downgrade", "0009_drop_avatar_path")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"
    cur = _alembic("current")
    assert "0009_drop_avatar_path" in cur.stdout

    up = _alembic("upgrade", "0010_pet_multi_provider")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"
    cur = _alembic("current")
    assert "0010_pet_multi_provider" in cur.stdout

    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
