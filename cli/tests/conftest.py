import os
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate ~/.config/myblog/ to a tempdir for every test."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    return tmp_path


@pytest.fixture
def tmp_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake repo root with a .env.deploy file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.deploy").write_text(
        "SERVER=root@example.com\nSSHPASS=secret\nDOMAIN=example.com\n"
    )
    monkeypatch.chdir(repo)
    return repo
