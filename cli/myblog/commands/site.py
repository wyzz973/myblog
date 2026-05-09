"""site get / set / theme commands.

Maps to: GET/PUT /api/admin/site, GET/PUT /api/admin/theme.
"""
from __future__ import annotations

import typer

from myblog import http, output

app = typer.Typer(help="Site identity / theme.")
theme = typer.Typer(help="Accent colors.")
app.add_typer(theme, name="theme")


@app.command("get")
def site_get() -> None:
    output.emit_record(http.admin_get("/site"))


@app.command("set")
def site_set(
    handle: str | None = typer.Option(None),
    tagline: str | None = typer.Option(None),
    email: str | None = typer.Option(None),
    github: str | None = typer.Option(None),
    footer_note: str | None = typer.Option(None),
    icp_beian: str | None = typer.Option(None),
    default_theme: str | None = typer.Option(None, help="dark | light"),
    launched_at: str | None = typer.Option(None, help="ISO date YYYY-MM-DD"),
) -> None:
    """PUT /api/admin/site with only the fields you pass."""
    payload = {
        k: v for k, v in {
            "handle": handle, "tagline": tagline, "email": email, "github": github,
            "footer_note": footer_note, "icp_beian": icp_beian,
            "default_theme": default_theme, "launched_at": launched_at,
        }.items() if v is not None
    }
    if not payload:
        output.emit_error("Pass at least one --field value", code=2)
        raise typer.Exit(code=2)
    output.emit_record(http.admin_put("/site", json=payload))


@theme.command("get")
def theme_get() -> None:
    output.emit_record(http.admin_get("/theme"))


@theme.command("set")
def theme_set(
    accent: str | None = typer.Option(None, "--accent"),
    accent2: str | None = typer.Option(None, "--accent2"),
    violet: str | None = typer.Option(None, "--violet"),
    danger: str | None = typer.Option(None, "--danger"),
) -> None:
    payload = {
        k: v for k, v in {
            "accent_color": accent, "accent2_color": accent2,
            "violet_color": violet, "danger_color": danger,
        }.items() if v is not None
    }
    if not payload:
        output.emit_error("Pass at least one --accent/--accent2/--violet/--danger", code=2)
        raise typer.Exit(code=2)
    output.emit_record(http.admin_put("/theme", json=payload))
