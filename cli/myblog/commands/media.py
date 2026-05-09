"""media upload/list/rm."""
from __future__ import annotations

from pathlib import Path

import typer

from myblog import http, output, safety

app = typer.Typer(help="Media files.")


@app.command("list")
def media_list(limit: int = typer.Option(50, min=1, max=200)) -> None:
    data = http.admin_get("/media", params={"limit": limit}) or []
    rows = data if isinstance(data, list) else data.get("items", [])
    output.emit_table(
        title="media",
        columns=["id", "filename", "url", "alt"],
        rows=rows,
    )


@app.command("upload")
def media_upload(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    alt: str | None = typer.Option(None, "--alt"),
) -> None:
    fields = {"alt": alt} if alt else None
    output.emit_record(http.admin_upload("/media", file_path=file, fields=fields))


@app.command("rm")
def media_rm(
    media_id: int,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="", summary=f"DELETE /media/{media_id}")
    http.admin_delete(f"/media/{media_id}")
    output.emit_message(f"deleted media {media_id}")
