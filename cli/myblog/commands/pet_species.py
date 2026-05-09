"""pet species list/add/edit/rm — wired under the existing pet subapp."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from myblog import http, output, safety

species = typer.Typer(help="Pet species (cat / dog / fox …).")


@species.command("list")
def list_() -> None:
    rows = http.admin_get("/pet/species") or []
    output.emit_table(
        title="pet species",
        columns=["id", "name", "color", "sort_order", "visible"],
        rows=rows,
    )


@species.command("add")
def add(from_json: Path = typer.Option(..., "--from-json", exists=True, dir_okay=False)) -> None:
    payload = json.loads(from_json.read_text())
    output.emit_record(http.admin_post("/pet/species", json=payload))


@species.command("edit")
def edit(
    species_id: str,
    from_json: Path = typer.Option(..., "--from-json", exists=True, dir_okay=False),
) -> None:
    payload = json.loads(from_json.read_text())
    output.emit_record(http.admin_patch(f"/pet/species/{species_id}", json=payload))


@species.command("rm")
def rm(
    species_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="", summary=f"DELETE /pet/species/{species_id}")
    http.admin_delete(f"/pet/species/{species_id}")
    output.emit_message(f"deleted species {species_id}")
