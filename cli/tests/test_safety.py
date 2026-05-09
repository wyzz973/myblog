import pytest
import typer
from typer.testing import CliRunner

from myblog import safety


def _build_app(tier: str):
    app = typer.Typer()

    @app.callback()
    def _root() -> None:
        """Force subcommand mode so 'kill' is parsed as a subcommand."""

    @app.command()
    def kill(
        target: str,
        yes: bool = typer.Option(False, "--yes"),
        confirm: str = typer.Option("", "--confirm"),
        dry_run: bool = typer.Option(False, "--dry-run"),
    ) -> None:
        safety.gate(tier, dry_run=dry_run, yes=yes, confirm=confirm, summary=f"would delete {target}")
        typer.echo(f"deleted {target}")

    return app


def test_l2_default_dryrun_blocks() -> None:
    runner = CliRunner()
    res = runner.invoke(_build_app("L2"), ["kill", "x"])
    assert res.exit_code == 1
    assert "dry-run" in res.stdout.lower()
    assert "would delete x" in res.stdout


def test_l2_with_yes_passes() -> None:
    runner = CliRunner()
    res = runner.invoke(_build_app("L2"), ["kill", "x", "--yes"])
    assert res.exit_code == 0
    assert "deleted x" in res.stdout


def test_l3_requires_confirm_phrase() -> None:
    runner = CliRunner()
    res = runner.invoke(_build_app("L3"), ["kill", "x", "--yes"])
    assert res.exit_code == 1
    assert "I understand" in res.stdout

    res2 = runner.invoke(_build_app("L3"), ["kill", "x", "--confirm", "I understand"])
    assert res2.exit_code == 0


def test_unknown_tier_raises() -> None:
    with pytest.raises(ValueError):
        safety.gate("L9", dry_run=False, yes=True, confirm="", summary="")
