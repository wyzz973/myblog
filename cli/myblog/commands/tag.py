"""tag list/add/rename/delete."""
from __future__ import annotations

import typer

from myblog import http, output, safety

app = typer.Typer(help="Tags.")


@app.command("list")
def tag_list() -> None:
    rows = http.admin_get("/tags") or []
    output.emit_table(
        title="tags",
        columns=["id", "label", "color", "sort_order"],
        rows=rows,
    )


@app.command("add")
def tag_add(
    id: str = typer.Option(..., "--id"),
    label: str = typer.Option(..., "--label"),
    color: str | None = typer.Option(None, "--color"),
) -> None:
    payload: dict = {"id": id, "label": label}
    if color:
        payload["color"] = color
    output.emit_record(http.admin_post("/tags", json=payload))


@app.command("rename")
def tag_rename(
    tag_id: str,
    label: str | None = typer.Option(None, "--label"),
    color: str | None = typer.Option(None, "--color"),
) -> None:
    payload: dict = {}
    if label is not None:
        payload["label"] = label
    if color is not None:
        payload["color"] = color
    if not payload:
        output.emit_error("Pass --label or --color", code=2)
        raise typer.Exit(code=2)
    output.emit_record(http.admin_patch(f"/tags/{tag_id}", json=payload))


@app.command("delete")
def tag_delete(
    tag_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="", summary=f"DELETE /tags/{tag_id}")
    http.admin_delete(f"/tags/{tag_id}")
    output.emit_message(f"deleted tag {tag_id}")
