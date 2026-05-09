"""auth login / whoami / token-set."""
from __future__ import annotations

import typer

from myblog import config, http, output

app = typer.Typer(help="Manage CLI credentials.")


@app.command()
def login() -> None:
    """Interactively store base_url + admin_token in ~/.config/myblog/credentials.toml."""
    base_url = typer.prompt("base_url (e.g. https://your-blog.example)").strip().rstrip("/")
    token = typer.prompt("admin_token", hide_input=True).strip()
    if not token:
        output.emit_error("admin_token is required", code=2)
        raise typer.Exit(code=2)
    config.save_credentials(base_url=base_url, admin_token=token)
    output.emit_message(f"Saved credentials → {config.credentials_path()}")


@app.command("token-set")
def token_set(token: str) -> None:
    """Non-interactive token replace (for CI)."""
    cur = config.load_credentials()
    config.save_credentials(base_url=cur.base_url, admin_token=token)
    output.emit_message("Token updated.")


@app.command()
def whoami() -> None:
    """Verify the configured token by calling GET /api/admin/site."""
    creds = config.load_credentials()
    try:
        site = http.admin_get("/site")
    except http.ApiError as e:
        output.emit_error(f"{e.status} {e.detail}", code=1)
        raise typer.Exit(code=1)
    output.emit_record({
        "base_url": creds.base_url,
        "ok": True,
        "site_handle": site.get("handle") if isinstance(site, dict) else None,
    })
