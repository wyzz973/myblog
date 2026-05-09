from pathlib import Path
from unittest.mock import MagicMock

import pytest

from myblog import ssh


def test_ssh_command_with_password(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[list[str]] = []

    def fake_run(cmd, **kw):
        seen.append(cmd)
        return MagicMock(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(ssh.subprocess, "run", fake_run)
    rc, out, err = ssh.run_ssh("uptime")
    assert rc == 0
    assert seen[0][0] == "sshpass"
    assert "-e" in seen[0]
    assert "root@example.com" in seen[0]
    assert seen[0][-1] == "uptime"


def test_ssh_without_sshpass_when_no_password(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env.deploy").write_text("SERVER=root@example.com\nDOMAIN=example.com\n")
    monkeypatch.chdir(repo)
    seen: list[list[str]] = []
    monkeypatch.setattr(ssh.subprocess, "run", lambda cmd, **kw: seen.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    ssh.run_ssh("uptime")
    assert seen[0][0] == "ssh"


def test_run_script_streams(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[str]] = []

    class FakeProc:
        returncode = 0
        def wait(self) -> int: return 0

    def fake_popen(cmd, **kw):
        captured.append(cmd)
        return FakeProc()

    monkeypatch.setattr(ssh.subprocess, "Popen", fake_popen)
    rc = ssh.run_local_script("./scripts/deploy.sh", ["--code-only"])
    assert rc == 0
    assert captured[0] == ["./scripts/deploy.sh", "--code-only"]


def test_scp_pull(tmp_repo: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: list[list[str]] = []
    monkeypatch.setattr(ssh.subprocess, "run", lambda cmd, **kw: seen.append(cmd) or MagicMock(returncode=0, stdout="", stderr=""))
    out = tmp_path / "dump.sql"
    ssh.scp_pull("/tmp/dump.sql", out)
    assert seen[0][0] == "sshpass"
    assert "root@example.com:/tmp/dump.sql" in " ".join(seen[0])
    assert str(out) in seen[0]
