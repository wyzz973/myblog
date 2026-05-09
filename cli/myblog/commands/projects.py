"""projects list / add / set / rm."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from myblog import http, output, safety

app = typer.Typer(help="Featured projects.")


@app.command("list")
def projects_list() -> None:
    rows = http.admin_get("/projects") or []
    output.emit_table(
        title="projects",
        columns=["name", "url", "blurb", "sort_order"],
        rows=rows,
    )


@app.command("add")
def projects_add(from_json: Path = typer.Option(..., "--from-json", exists=True, dir_okay=False)) -> None:
    payload = json.loads(from_json.read_text())
    output.emit_record(http.admin_post("/projects", json=payload))


@app.command("set")
def projects_set(
    name: str,
    url: str | None = typer.Option(None),
    blurb: str | None = typer.Option(None),
    from_json: Path | None = typer.Option(None, "--from-json", exists=True, dir_okay=False),
) -> None:
    if from_json is not None:
        payload = json.loads(from_json.read_text())
    else:
        payload = {k: v for k, v in {"url": url, "blurb": blurb}.items() if v is not None}
        if not payload:
            output.emit_error("Pass --from-json or at least one --url/--blurb", code=2)
            raise typer.Exit(code=2)
    output.emit_record(http.admin_patch(f"/projects/{name}", json=payload))


@app.command("rm")
def projects_rm(
    name: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="", summary=f"DELETE /projects/{name}")
    http.admin_delete(f"/projects/{name}")
    output.emit_message(f"deleted project {name}")
