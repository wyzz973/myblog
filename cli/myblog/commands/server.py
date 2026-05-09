"""server logs / restart / status / ssh / migrate / backup / shell.

Migrate / backup / shell are added in tasks 17-19.
"""
from __future__ import annotations

from pathlib import Path

import typer

from myblog import output, safety, ssh

app = typer.Typer(help="Server ops via SSH.")
SERVICES = {
    "api": "myblog-api",
    "worker": "myblog-worker",
    "nginx": "nginx",
}


@app.command("status")
def status() -> None:
    """systemctl is-active for the four services we care about."""
    cmd = "systemctl is-active myblog-api myblog-worker postgresql redis-server nginx; true"
    rc, out, err = ssh.run_ssh(cmd)
    lines = out.strip().splitlines()
    names = ["myblog-api", "myblog-worker", "postgresql", "redis-server", "nginx"]
    rows = [
        {"service": n, "state": (lines[i] if i < len(lines) else "?")}
        for i, n in enumerate(names)
    ]
    output.emit_table(title="services", columns=["service", "state"], rows=rows)


@app.command("logs")
def logs(
    service: str = typer.Argument(..., help="api|worker|nginx"),
    tail: int = typer.Option(50, "--tail"),
    follow: bool = typer.Option(False, "--follow"),
) -> None:
    if service not in SERVICES:
        output.emit_error(f"service must be one of {sorted(SERVICES)}", code=2)
        raise typer.Exit(code=2)
    unit = SERVICES[service]
    if service == "nginx":
        if follow:
            cmd = f"tail -F -n {tail} /var/log/nginx/error.log /var/log/nginx/access.log"
            rc = ssh.run_ssh_streaming(cmd)
            raise typer.Exit(code=rc)
        cmd = f"tail -n {tail} /var/log/nginx/error.log /var/log/nginx/access.log"
    else:
        if follow:
            cmd = f"journalctl -u {unit} -n {tail} -f"
            rc = ssh.run_ssh_streaming(cmd)
            raise typer.Exit(code=rc)
        cmd = f"journalctl -u {unit} -n {tail} --no-pager"
    rc, out, err = ssh.run_ssh(cmd)
    typer.echo(out)
    if err:
        typer.echo(err, err=True)
    raise typer.Exit(code=rc)


@app.command("restart")
def restart(
    service: str = typer.Argument(..., help="api|worker"),
    yes: bool = typer.Option(False, "--yes"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    if service not in ("api", "worker"):
        output.emit_error("service must be api or worker", code=2)
        raise typer.Exit(code=2)
    unit = SERVICES[service]
    safety.gate("L2", dry_run=dry_run, yes=yes, confirm="",
                summary=f"systemctl restart {unit}")
    rc, out, err = ssh.run_ssh(f"systemctl restart {unit}")
    if rc != 0:
        output.emit_error(err.strip() or "restart failed", code=1)
        raise typer.Exit(code=rc)
    output.emit_message(f"restarted {unit}")


@app.command("ssh")
def ssh_passthrough(
    cmd: str = typer.Argument(..., help='Remote command, e.g. "uptime"'),
) -> None:
    """Execute an arbitrary command on the server."""
    rc, out, err = ssh.run_ssh(cmd, capture=True, timeout=120)
    if out:
        typer.echo(out, nl=False)
    if err:
        typer.echo(err, err=True, nl=False)
    raise typer.Exit(code=rc)


migrate = typer.Typer(help="alembic migrations on the server.")
app.add_typer(migrate, name="migrate")

_REMOTE_BACKEND = "/opt/myblog/repo/backend"
_ALEMBIC = (
    f"sudo -u myblog -H bash -lc 'cd {_REMOTE_BACKEND} && set -a && . .env && set +a"
    " && .venv/bin/alembic {sub}'"
)


def _alembic(sub: str) -> tuple[int, str, str]:
    return ssh.run_ssh(_ALEMBIC.format(sub=sub), timeout=180)


@migrate.command("status")
def migrate_status() -> None:
    rc, out, err = _alembic("current")
    typer.echo(out)
    if err: typer.echo(err, err=True)
    raise typer.Exit(code=rc)


@migrate.command("up")
def migrate_up() -> None:
    rc, out, err = _alembic("upgrade head")
    typer.echo(out)
    if err: typer.echo(err, err=True)
    raise typer.Exit(code=rc)


@migrate.command("down")
def migrate_down(
    revision: str = typer.Argument(..., help="Target revision id, e.g. 0019"),
    confirm: str = typer.Option("", "--confirm"),
) -> None:
    safety.gate("L3", dry_run=False, yes=True, confirm=confirm,
                summary=f"alembic downgrade {revision}")
    rc, out, err = _alembic(f"downgrade {revision}")
    typer.echo(out)
    if err: typer.echo(err, err=True)
    raise typer.Exit(code=rc)


import datetime as _dt
import shlex

backup = typer.Typer(help="DB / media backups.")
app.add_typer(backup, name="backup")
restore = typer.Typer(help="Destructive restore.")
backup.add_typer(restore, name="restore")


def _stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%dT%H%M%S")


@backup.command("db")
def backup_db(
    out: Path | None = typer.Option(None, "--out", help="Output .sql.gz path"),
) -> None:
    remote = f"/tmp/myblog-db-{_stamp()}.sql.gz"
    cmd = (
        f"sudo -u postgres -H bash -lc 'pg_dump -Fc myblog | gzip > {shlex.quote(remote)}'"
    )
    rc, _, err = ssh.run_ssh(cmd, timeout=600)
    if rc != 0:
        output.emit_error(err.strip() or "pg_dump failed", code=1)
        raise typer.Exit(code=rc)
    out = out or Path.cwd() / Path(remote).name
    rc2 = ssh.scp_pull(remote, out)
    ssh.run_ssh(f"rm -f {shlex.quote(remote)}", timeout=30)
    if rc2 != 0:
        output.emit_error("scp pull failed", code=1)
        raise typer.Exit(code=rc2)
    output.emit_message(f"saved {out}")


@backup.command("media")
def backup_media(
    out: Path | None = typer.Option(None, "--out", help="Output .tgz path"),
) -> None:
    remote = f"/tmp/myblog-media-{_stamp()}.tgz"
    cmd = (
        f"tar -C /opt/myblog -czf {shlex.quote(remote)} media"
    )
    rc, _, err = ssh.run_ssh(cmd, timeout=600)
    if rc != 0:
        output.emit_error(err.strip() or "tar failed", code=1)
        raise typer.Exit(code=rc)
    out = out or Path.cwd() / Path(remote).name
    rc2 = ssh.scp_pull(remote, out)
    ssh.run_ssh(f"rm -f {shlex.quote(remote)}", timeout=30)
    if rc2 != 0:
        output.emit_error("scp pull failed", code=1)
        raise typer.Exit(code=rc2)
    output.emit_message(f"saved {out}")


@restore.command("db")
def restore_db(
    file: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    confirm: str = typer.Option("", "--confirm"),
) -> None:
    safety.gate("L3", dry_run=False, yes=True, confirm=confirm,
                summary=f"pg_restore --clean myblog from {file.name}")
    output.emit_error(
        "restore is interactive and operator-confirmed; not implemented in v1. "
        "Manual recipe: scp the dump to the server, then "
        "sudo -u postgres pg_restore --clean -d myblog <file>.",
        code=2,
    )
    raise typer.Exit(code=2)
