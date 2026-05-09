"""deploy full / code / front — wraps scripts/deploy.sh."""
from __future__ import annotations

import typer

from myblog import config, output, ssh

app = typer.Typer(help="Deploy the blog.")


def _run(args: list[str]) -> int:
    config.load_deploy_env()  # sanity: raises NotConfigured if .env.deploy missing
    repo = config.find_repo_root()
    script = repo / "scripts" / "deploy.sh"
    if not script.exists():
        output.emit_error(f"{script} not found", code=2)
        raise typer.Exit(code=2)
    return ssh.run_local_script(str(script), args)


@app.command("full")
def deploy_full() -> None:
    """rsync code + dist + migrate + restart."""
    rc = _run([])
    raise typer.Exit(code=rc)


@app.command("code")
def deploy_code() -> None:
    """Backend code only (no frontend rebuild)."""
    rc = _run(["--code-only"])
    raise typer.Exit(code=rc)


@app.command("front")
def deploy_front() -> None:
    """Frontend dist only (no backend changes)."""
    rc = _run(["--frontend-only"])
    raise typer.Exit(code=rc)
