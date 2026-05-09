"""skill install / uninstall / status — link skills/myblog/ into Claude Code."""
from __future__ import annotations

from pathlib import Path

import typer

from myblog import config, output

app = typer.Typer(help="Install agent skill for Claude Code.")


def _source_dir() -> Path:
    src = config.find_repo_root() / "skills" / "myblog"
    if not (src / "SKILL.md").exists():
        raise typer.Exit(code=2)
    return src


def _target_dir(scope: str) -> Path:
    if scope == "user":
        return Path.home() / ".claude" / "skills" / "myblog"
    if scope == "project":
        return config.find_repo_root() / ".claude" / "skills" / "myblog"
    raise ValueError(f"scope must be user|project, got {scope!r}")


def _parse_frontmatter(skill_md: Path) -> dict:
    text = skill_md.read_text()
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm: dict = {}
    for line in text[3:end].splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        fm[k.strip()] = v.strip()
    return fm


@app.command("install")
def install(
    scope: str = typer.Option("user", "--scope", help="user|project"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    try:
        src = _source_dir()
    except typer.Exit:
        output.emit_error("skills/myblog/SKILL.md not found in repo", code=2)
        raise typer.Exit(code=2)
    target = _target_dir(scope)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        if not force:
            output.emit_error(
                f"{target} already exists. Re-run with --force to replace.", code=2
            )
            raise typer.Exit(code=2)
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            import shutil

            shutil.rmtree(target)
    target.symlink_to(src, target_is_directory=True)
    output.emit_message(f"linked {target} -> {src}")


@app.command("uninstall")
def uninstall(scope: str = typer.Option("user", "--scope")) -> None:
    target = _target_dir(scope)
    if target.is_symlink() or target.exists():
        if target.is_symlink() or target.is_file():
            target.unlink()
        else:
            import shutil

            shutil.rmtree(target)
        output.emit_message(f"removed {target}")
        return
    output.emit_message(f"{target} did not exist; nothing to do.")


@app.command("status")
def status() -> None:
    src = config.find_repo_root() / "skills" / "myblog"
    skill_md = src / "SKILL.md"
    fm = _parse_frontmatter(skill_md) if skill_md.exists() else {}
    user_t = Path.home() / ".claude" / "skills" / "myblog"
    proj_t = config.find_repo_root() / ".claude" / "skills" / "myblog"
    output.emit_record(
        {
            "name": fm.get("name", ""),
            "description": fm.get("description", ""),
            "source": str(src),
            "user_installed": user_t.exists() or user_t.is_symlink(),
            "project_installed": proj_t.exists() or proj_t.is_symlink(),
        }
    )
