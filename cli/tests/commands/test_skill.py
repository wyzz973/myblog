import json as _json
from pathlib import Path

from typer.testing import CliRunner

from myblog.__main__ import app


def _seed_skill_source(tmp_repo: Path) -> Path:
    src = tmp_repo / "skills" / "myblog"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(
        "---\nname: myblog\ndescription: stub\n---\n\n# Hi\n"
    )
    return src


def test_install_user_scope(tmp_home: Path, tmp_repo: Path) -> None:
    src = _seed_skill_source(tmp_repo)
    res = CliRunner().invoke(app, ["skill", "install"])
    assert res.exit_code == 0, res.stdout
    target = tmp_home / ".claude" / "skills" / "myblog"
    assert target.is_symlink()
    assert target.resolve() == src.resolve()


def test_install_project_scope(tmp_home: Path, tmp_repo: Path) -> None:
    src = _seed_skill_source(tmp_repo)
    res = CliRunner().invoke(app, ["skill", "install", "--scope", "project"])
    assert res.exit_code == 0
    target = tmp_repo / ".claude" / "skills" / "myblog"
    assert target.is_symlink()
    assert target.resolve() == src.resolve()


def test_install_existing_without_force_errors(tmp_home: Path, tmp_repo: Path) -> None:
    _seed_skill_source(tmp_repo)
    runner = CliRunner()
    runner.invoke(app, ["skill", "install"])
    res = runner.invoke(app, ["skill", "install"])
    assert res.exit_code == 2
    assert "already exists" in res.stdout or "already exists" in res.stderr


def test_install_force_replaces(tmp_home: Path, tmp_repo: Path) -> None:
    _seed_skill_source(tmp_repo)
    runner = CliRunner()
    runner.invoke(app, ["skill", "install"])
    res = runner.invoke(app, ["skill", "install", "--force"])
    assert res.exit_code == 0


def test_uninstall_removes_link(tmp_home: Path, tmp_repo: Path) -> None:
    _seed_skill_source(tmp_repo)
    runner = CliRunner()
    runner.invoke(app, ["skill", "install"])
    target = tmp_home / ".claude" / "skills" / "myblog"
    assert target.exists()
    res = runner.invoke(app, ["skill", "uninstall"])
    assert res.exit_code == 0
    assert not target.exists()


def test_status_reports_user_install(tmp_home: Path, tmp_repo: Path) -> None:
    _seed_skill_source(tmp_repo)
    runner = CliRunner()
    runner.invoke(app, ["skill", "install"])
    res = runner.invoke(app, ["--json", "skill", "status"])
    obj = _json.loads(res.stdout.splitlines()[0])
    assert obj["user_installed"] is True
    assert obj["project_installed"] is False
    assert obj["name"] == "myblog"
