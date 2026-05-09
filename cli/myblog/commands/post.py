"""post list/get/new/edit/publish/unpublish/delete/from-md."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import typer

from myblog import http, output, safety

app = typer.Typer(help="Posts.")


@app.command("list")
def post_list(
    status: str = typer.Option("all", help="all|draft|published|scheduled"),
    tag: str | None = typer.Option(None),
    q: str | None = typer.Option(None, help="search title/summary/body"),
    limit: int = typer.Option(20, min=1, max=100),
    offset: int = typer.Option(0, min=0),
) -> None:
    params: dict = {"status": status, "limit": limit, "offset": offset}
    if tag:
        params["tag"] = tag
    if q:
        params["q"] = q
    data = http.admin_get("/posts", params=params)
    output.emit_table(
        title=f"posts (total={data.get('total', 0)})",
        columns=["id", "title", "tag", "status", "date"],
        rows=data.get("items", []),
    )


@app.command("get")
def post_get(post_id: str) -> None:
    output.emit_record(http.admin_get(f"/posts/{post_id}"))


@app.command("new")
def post_new(
    title: str = typer.Option(..., "--title"),
    tag: str = typer.Option(..., "--tag"),
    subtitle: str | None = typer.Option(None, "--subtitle"),
    draft: bool = typer.Option(False, "--draft"),
    body: str = typer.Option("", "--body", help="optional initial body markdown"),
) -> None:
    """Build a stub markdown post and POST /posts."""
    n = http.admin_get("/posts/next-n").get("n", "001")
    slug = title.lower().replace(" ", "-").strip("-")[:48] or "untitled"
    pid = f"{n}-{slug}"
    today = _dt.date.today().isoformat()
    fm_lines = [
        "---",
        f"id: {pid}",
        f"n: {n}",
        f"title: {title}",
        f"tag: {tag}",
        f"date: {today}",
    ]
    if subtitle:
        fm_lines.append(f"subtitle: {subtitle}")
    if draft:
        fm_lines.append("status: draft")
    fm_lines.append("---")
    md = "\n".join(fm_lines) + "\n" + (body or "")
    output.emit_record(http.admin_post("/posts", json={"markdown": md}))


@app.command("edit")
def post_edit(
    post_id: str,
    title: str | None = typer.Option(None),
    subtitle: str | None = typer.Option(None),
    tag: str | None = typer.Option(None),
    summary: str | None = typer.Option(None),
    body_file: Path | None = typer.Option(
        None, "--body-file", exists=True, dir_okay=False, readable=True
    ),
    featured: bool | None = typer.Option(None),
    private: bool | None = typer.Option(None),
    comments_enabled: bool | None = typer.Option(None, "--comments-enabled"),
) -> None:
    payload: dict = {}
    for key, val in [
        ("title", title),
        ("subtitle", subtitle),
        ("tag", tag),
        ("summary", summary),
        ("featured", featured),
        ("private", private),
        ("comments_enabled", comments_enabled),
    ]:
        if val is not None:
            payload[key] = val
    if body_file is not None:
        payload["body_md"] = body_file.read_text()
    if not payload:
        output.emit_error("Pass at least one field to edit", code=2)
        raise typer.Exit(code=2)
    output.emit_record(http.admin_patch(f"/posts/{post_id}", json=payload))


@app.command("publish")
def post_publish(post_id: str) -> None:
    output.emit_record(http.admin_patch(f"/posts/{post_id}", json={"status": "published"}))


@app.command("unpublish")
def post_unpublish(post_id: str) -> None:
    output.emit_record(http.admin_patch(f"/posts/{post_id}", json={"status": "draft"}))


@app.command("delete")
def post_delete(
    post_id: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="", summary=f"DELETE /posts/{post_id}")
    http.admin_delete(f"/posts/{post_id}")
    output.emit_message(f"deleted {post_id}")


@app.command("from-md")
def post_from_md(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite if id already exists"),
) -> None:
    md = file.read_text()
    params = {"overwrite": "true"} if overwrite else None
    output.emit_record(http.admin_post("/posts", json={"markdown": md}, params=params))
