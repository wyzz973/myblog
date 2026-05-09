"""Danger tier gates for destructive commands.

L1: free pass; do not call gate().
L2: default --dry-run; --yes to actually run.
L3: must pass --confirm "I understand".
"""
from __future__ import annotations

from typing import Literal

import typer

Tier = Literal["L2", "L3"]
CONFIRM_PHRASE = "I understand"


def gate(
    tier: str,
    *,
    dry_run: bool,
    yes: bool,
    confirm: str,
    summary: str,
) -> None:
    """Stop execution unless the right gate is satisfied.

    Prints the summary in dry-run mode so the user / agent sees what would happen.
    """
    if tier not in ("L2", "L3"):
        raise ValueError(f"Unknown danger tier: {tier!r}")

    if tier == "L3":
        if confirm != CONFIRM_PHRASE:
            typer.echo(
                f'[L3] Refusing to proceed without --confirm "{CONFIRM_PHRASE}". '
                f"Action: {summary}"
            )
            raise typer.Exit(code=1)
        return

    # L2
    if dry_run or not yes:
        typer.echo(f"[L2 dry-run] {summary}")
        typer.echo("Re-run with --yes to actually execute.")
        raise typer.Exit(code=1)
