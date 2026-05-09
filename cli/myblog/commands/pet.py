"""pet config / personality / memory / timeline."""
from __future__ import annotations

import json
from pathlib import Path

import typer

from myblog import http, output, safety

app = typer.Typer(help="Pet config + memory.")
config_app = typer.Typer(help="PetConfig get/set.")
personality_app = typer.Typer(help="Personas + mode templates.")
memory_app = typer.Typer(help="Conversation memory.")
timeline_app = typer.Typer(help="Pet timeline events.")
app.add_typer(config_app, name="config")
app.add_typer(personality_app, name="personality")
app.add_typer(memory_app, name="memory")
app.add_typer(timeline_app, name="timeline")

from myblog.commands.pet_species import species as species_app  # noqa: E402
app.add_typer(species_app, name="species")


@config_app.command("get")
def cfg_get() -> None:
    output.emit_record(http.admin_get("/pet"))


@config_app.command("set")
def cfg_set(from_json: Path = typer.Option(..., "--from-json", exists=True, dir_okay=False)) -> None:
    payload = json.loads(from_json.read_text())
    output.emit_record(http.admin_put("/pet", json=payload))


@personality_app.command("get")
def per_get() -> None:
    full = http.admin_get("/pet")
    slice_ = {k: full.get(k) for k in ("personas", "mode_templates")}
    output.emit_record(slice_)


@personality_app.command("set")
def per_set(from_json: Path = typer.Option(..., "--from-json", exists=True, dir_okay=False)) -> None:
    """Patch personas + mode_templates onto current PetConfig."""
    incoming = json.loads(from_json.read_text())
    full = http.admin_get("/pet")
    for k in ("personas", "mode_templates"):
        if k in incoming:
            full[k] = incoming[k]
    output.emit_record(http.admin_put("/pet", json=full))


@personality_app.command("reset")
def per_reset(
    section: str = typer.Argument(..., help="personas | templates | both"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    if section not in ("personas", "templates", "both"):
        output.emit_error("section must be personas|templates|both", code=2)
        raise typer.Exit(code=2)
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="",
                summary=f"POST /pet/reset?section={section}")
    output.emit_record(http.admin_post("/pet/reset", params={"section": section}))


@memory_app.command("list")
def mem_list(
    limit: int = typer.Option(50, min=1, max=200),
    species: str | None = typer.Option(None),
    q: str | None = typer.Option(None, help="search term"),
) -> None:
    params: dict = {"limit": limit}
    if species: params["species"] = species
    if q: params["q"] = q
    data = http.admin_get("/pet/conversations", params=params)
    output.emit_table(
        title="pet conversations",
        columns=["visitor_hash", "msg_count", "last_at", "species"],
        rows=data.get("items", []),
    )


@memory_app.command("get")
def mem_get(visitor_hash: str) -> None:
    output.emit_record(http.admin_get(f"/pet/conversations/{visitor_hash}"))


@memory_app.command("clear")
def mem_clear(
    visitor_hash: str,
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="",
                summary=f"DELETE /pet/conversations/{visitor_hash}")
    http.admin_delete(f"/pet/conversations/{visitor_hash}")
    output.emit_message(f"cleared conversation {visitor_hash}")


@timeline_app.command("list")
def tl_list(
    visitor_hash: str = typer.Argument(...),
    limit: int = typer.Option(50, min=1, max=200),
) -> None:
    """Read full conversation thread for one visitor."""
    data = http.admin_get(f"/pet/conversations/{visitor_hash}", params={"limit": limit})
    output.emit_record(data)
