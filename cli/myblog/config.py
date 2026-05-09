"""Load CLI credentials and project deploy env.

Two stores:
  ~/.config/myblog/credentials.toml      (HTTP admin token)
  $REPO/.env.deploy                       (SERVER / SSHPASS / DOMAIN)
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w


class NotConfigured(RuntimeError):
    """Raised when a required config file is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Credentials:
    base_url: str
    admin_token: str


@dataclass(frozen=True, slots=True)
class DeployEnv:
    server: str
    sshpass: str | None
    domain: str | None


def credentials_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "myblog" / "credentials.toml"


def load_credentials() -> Credentials:
    p = credentials_path()
    if not p.exists():
        raise NotConfigured(
            f"{p} not found — run `myblog auth login` to create it."
        )
    data = tomllib.loads(p.read_text())
    base_url = data.get("base_url")
    admin_token = data.get("admin_token")
    if not base_url or not admin_token:
        raise NotConfigured(
            f"{p} is missing base_url or admin_token; re-run `myblog auth login`."
        )
    return Credentials(base_url=str(base_url).rstrip("/"), admin_token=str(admin_token))


def save_credentials(*, base_url: str, admin_token: str) -> None:
    p = credentials_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(tomli_w.dumps({"base_url": base_url, "admin_token": admin_token}).encode())
    p.chmod(0o600)


def find_repo_root(start: Path | None = None) -> Path:
    cur = (start or Path.cwd()).resolve()
    for cand in [cur, *cur.parents]:
        if (cand / ".env.deploy").exists() or (cand / ".git").exists():
            return cand
    raise NotConfigured(
        "Repo root not found (no .env.deploy or .git up the tree). "
        "Run from inside the MyBlog repo."
    )


def load_deploy_env() -> DeployEnv:
    root = find_repo_root()
    p = root / ".env.deploy"
    if not p.exists():
        raise NotConfigured(
            f"{p} not found. Create it with SERVER=, SSHPASS=, DOMAIN= "
            "(see scripts/deploy.sh)."
        )
    fields: dict[str, str] = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        fields[k.strip()] = v.strip().strip('"').strip("'")
    server = fields.get("SERVER")
    if not server:
        raise NotConfigured(f"{p} missing SERVER=")
    return DeployEnv(
        server=server,
        sshpass=fields.get("SSHPASS") or None,
        domain=fields.get("DOMAIN") or None,
    )
