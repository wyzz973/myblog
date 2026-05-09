"""ssh / rsync / scp subprocess wrappers using .env.deploy."""
from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path

from myblog import config


def _env_with_sshpass(env_extra: dict[str, str] | None = None) -> tuple[list[str], dict[str, str]]:
    """Return (prefix_argv, env) — prefixes `sshpass -e` if SSHPASS configured."""
    deploy = config.load_deploy_env()
    env = os.environ.copy()
    prefix: list[str] = []
    if deploy.sshpass:
        prefix = ["sshpass", "-e"]
        env["SSHPASS"] = deploy.sshpass
    if env_extra:
        env.update(env_extra)
    return prefix, env


def run_ssh(remote_cmd: str, *, capture: bool = True, timeout: float = 60.0) -> tuple[int, str, str]:
    """Run a single command on the remote server. Returns (rc, stdout, stderr)."""
    deploy = config.load_deploy_env()
    prefix, env = _env_with_sshpass()
    argv = [
        *prefix, "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "BatchMode=no",
        deploy.server, remote_cmd,
    ]
    proc = subprocess.run(
        argv,
        capture_output=capture,
        text=True,
        env=env,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def run_ssh_streaming(remote_cmd: str) -> int:
    """Run ssh and stream output live (used for `logs --follow`, `shell`)."""
    deploy = config.load_deploy_env()
    prefix, env = _env_with_sshpass()
    argv = [
        *prefix, "ssh",
        "-o", "StrictHostKeyChecking=accept-new",
        "-t",  # PTY for live tail / interactive
        deploy.server, remote_cmd,
    ]
    proc = subprocess.Popen(argv, env=env)
    return proc.wait()


def run_local_script(path: str, args: list[str]) -> int:
    """Invoke a local script (e.g. scripts/deploy.sh) and stream output."""
    proc = subprocess.Popen([path, *args])
    return proc.wait()


def scp_pull(remote_path: str, local_path: Path) -> int:
    """Copy a file from the server to the local path."""
    deploy = config.load_deploy_env()
    prefix, env = _env_with_sshpass()
    argv = [
        *prefix, "scp",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{deploy.server}:{remote_path}",
        str(local_path),
    ]
    proc = subprocess.run(argv, env=env, capture_output=True, text=True)
    return proc.returncode


def quote(s: str) -> str:
    """Quote a shell argument for safe interpolation in remote_cmd strings."""
    return shlex.quote(s)
