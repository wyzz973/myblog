"""now list/add/set/rm — currently-listening / reading / playing entries."""
from __future__ import annotations

import typer

from myblog import http, output, safety

app = typer.Typer(help="Now-playing entries.")


@app.command("list")
def now_list() -> None:
    rows = http.admin_get("/now") or []
    output.emit_table(
        title="now",
        columns=["id", "kind", "label", "url", "sort_order"],
        rows=rows,
    )


@app.command("add")
def now_add(
    kind: str = typer.Option(..., "--kind", help="reading|listening|playing|watching"),
    label: str = typer.Option(..., "--label"),
    url: str | None = typer.Option(None, "--url"),
) -> None:
    payload: dict = {"kind": kind, "label": label}
    if url:
        payload["url"] = url
    output.emit_record(http.admin_post("/now", json=payload))


@app.command("set")
def now_set(
    entry_id: int,
    label: str | None = typer.Option(None),
    kind: str | None = typer.Option(None),
    url: str | None = typer.Option(None),
) -> None:
    payload = {k: v for k, v in {"label": label, "kind": kind, "url": url}.items() if v is not None}
    if not payload:
        output.emit_error("Pass at least one --label/--kind/--url", code=2)
        raise typer.Exit(code=2)
    output.emit_record(http.admin_patch(f"/now/{entry_id}", json=payload))


@app.command("rm")
def now_rm(
    entry_id: int,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="", summary=f"DELETE /now/{entry_id}")
    http.admin_delete(f"/now/{entry_id}")
    output.emit_message(f"deleted now entry {entry_id}")
