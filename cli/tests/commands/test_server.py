from pathlib import Path
from unittest.mock import MagicMock

from typer.testing import CliRunner

from myblog import ssh
from myblog.__main__ import app


def _patch_ssh(monkeypatch, *, rc=0, stdout="active", stderr=""):
    seen: list[str] = []

    def fake_run(cmd, **kw):
        seen.append(" ".join(cmd))
        return MagicMock(returncode=rc, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(ssh.subprocess, "run", fake_run)
    return seen


def test_status(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="active\nactive\nactive\nactive\nactive")
    res = CliRunner().invoke(app, ["server", "status"])
    assert res.exit_code == 0
    assert "myblog-api" in seen[0]
    assert "myblog-worker" in seen[0]
    assert "nginx" in seen[0]


def test_logs_invokes_journalctl(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="log line")
    res = CliRunner().invoke(app, ["server", "logs", "api", "--tail", "100"])
    assert res.exit_code == 0
    assert "journalctl" in seen[0]
    assert "myblog-api" in seen[0]
    assert "-n 100" in seen[0]


def test_restart_dry_run(tmp_home, tmp_repo, monkeypatch) -> None:
    res = CliRunner().invoke(app, ["server", "restart", "api"])
    assert res.exit_code == 1
    assert "dry-run" in res.stdout.lower()


def test_restart_yes(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="")
    res = CliRunner().invoke(app, ["server", "restart", "api", "--yes"])
    assert res.exit_code == 0
    assert "systemctl restart myblog-api" in seen[0]


def test_ssh_passthrough(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="hello")
    res = CliRunner().invoke(app, ["server", "ssh", "echo hello"])
    assert res.exit_code == 0
    assert "echo hello" in seen[0]


def test_migrate_up_runs_alembic(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="OK")
    res = CliRunner().invoke(app, ["server", "migrate", "up"])
    assert res.exit_code == 0
    assert "alembic upgrade head" in seen[0]
    assert "/opt/myblog/repo/backend" in seen[0]


def test_migrate_status(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="0020 (head)")
    res = CliRunner().invoke(app, ["server", "migrate", "status"])
    assert res.exit_code == 0
    assert "alembic current" in seen[0]


def test_migrate_down_requires_confirm(tmp_home, tmp_repo, monkeypatch) -> None:
    res = CliRunner().invoke(app, ["server", "migrate", "down", "0019"])
    assert res.exit_code == 1
    assert "I understand" in res.stdout


def test_migrate_down_with_confirm(tmp_home, tmp_repo, monkeypatch) -> None:
    seen = _patch_ssh(monkeypatch, stdout="downgraded")
    res = CliRunner().invoke(app, ["server", "migrate", "down", "0019", "--confirm", "I understand"])
    assert res.exit_code == 0
    assert "alembic downgrade 0019" in seen[0]
