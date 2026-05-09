from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from myblog import ssh
from myblog.__main__ import app


def _seed_repo(tmp_repo: Path) -> None:
    scripts = tmp_repo / "scripts"
    scripts.mkdir()
    (scripts / "deploy.sh").write_text("#!/bin/sh\necho ok\n")
    (scripts / "deploy.sh").chmod(0o755)


def test_deploy_full_invokes_script_no_args(tmp_home, tmp_repo, monkeypatch) -> None:
    _seed_repo(tmp_repo)
    seen: list[list[str]] = []

    def fake_popen(cmd, **kw):
        seen.append(cmd)
        m = MagicMock()
        m.wait.return_value = 0
        m.returncode = 0
        return m

    monkeypatch.setattr(ssh.subprocess, "Popen", fake_popen)
    res = CliRunner().invoke(app, ["deploy", "full"])
    assert res.exit_code == 0
    assert seen[0][0].endswith("scripts/deploy.sh")
    assert seen[0][1:] == []


def test_deploy_code(tmp_home, tmp_repo, monkeypatch) -> None:
    _seed_repo(tmp_repo)
    seen: list[list[str]] = []
    def fake_popen(cmd, **kw):
        seen.append(cmd)
        m = MagicMock(); m.wait.return_value = 0; m.returncode = 0
        return m
    monkeypatch.setattr(ssh.subprocess, "Popen", fake_popen)
    res = CliRunner().invoke(app, ["deploy", "code"])
    assert res.exit_code == 0
    assert seen[0][1:] == ["--code-only"]


def test_deploy_front(tmp_home, tmp_repo, monkeypatch) -> None:
    _seed_repo(tmp_repo)
    seen: list[list[str]] = []
    def fake_popen(cmd, **kw):
        seen.append(cmd)
        m = MagicMock(); m.wait.return_value = 0; m.returncode = 0
        return m
    monkeypatch.setattr(ssh.subprocess, "Popen", fake_popen)
    res = CliRunner().invoke(app, ["deploy", "front"])
    assert res.exit_code == 0
    assert seen[0][1:] == ["--frontend-only"]


def test_deploy_propagates_nonzero(tmp_home, tmp_repo, monkeypatch) -> None:
    _seed_repo(tmp_repo)
    def fake_popen(cmd, **kw):
        m = MagicMock(); m.wait.return_value = 2; m.returncode = 2
        return m
    monkeypatch.setattr(ssh.subprocess, "Popen", fake_popen)
    res = CliRunner().invoke(app, ["deploy", "full"])
    assert res.exit_code == 2
