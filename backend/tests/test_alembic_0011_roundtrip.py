"""Round-trip alembic to 0010 and back to 0011."""
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


def test_0011_downgrade_then_upgrade_clean():
    down = _alembic("downgrade", "0010_pet_multi_provider")
    assert down.returncode == 0, f"downgrade failed:\n{down.stderr}"
    cur = _alembic("current")
    assert "0010_pet_multi_provider" in cur.stdout

    up = _alembic("upgrade", "0011_pet_add_deepseek")
    assert up.returncode == 0, f"upgrade failed:\n{up.stderr}"
    cur = _alembic("current")
    assert "0011_pet_add_deepseek" in cur.stdout

    final = _alembic("upgrade", "head")
    assert final.returncode == 0, f"final upgrade failed:\n{final.stderr}"
