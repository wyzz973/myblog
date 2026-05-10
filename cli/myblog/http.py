"""Synchronous httpx wrapper for /api/admin/* with bearer auth."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from myblog import config

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


@dataclass(slots=True)
class ApiError(Exception):
    status: int
    detail: Any
    url: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"HTTP {self.status} {self.url}: {self.detail!r}"


def _client() -> tuple[httpx.Client, str]:
    creds = config.load_credentials()
    proxy = os.environ.get("MYBLOG_PROXY") or None
    client = httpx.Client(
        base_url=f"{creds.base_url}/api/admin",
        headers={"Authorization": f"Bearer {creds.admin_token}"},
        timeout=_TIMEOUT,
        trust_env=False,    # ignore HTTPS_PROXY/HTTP_PROXY by default
        proxy=proxy,        # but honor explicit MYBLOG_PROXY override
    )
    return client, creds.base_url


def _handle(resp: httpx.Response) -> Any:
    if resp.status_code == 204:
        return None
    if resp.status_code >= 400:
        try:
            payload = resp.json()
            detail = payload.get("detail", payload)
        except Exception:
            detail = resp.text
        raise ApiError(status=resp.status_code, detail=detail, url=str(resp.request.url))
    if not resp.content:
        return None
    return resp.json()


def admin_get(path: str, *, params: dict | None = None) -> Any:
    client, _ = _client()
    with client:
        return _handle(client.get(path, params=params))


def admin_post(path: str, *, json: dict | None = None, params: dict | None = None) -> Any:
    client, _ = _client()
    with client:
        return _handle(client.post(path, json=json, params=params))


def admin_patch(path: str, *, json: dict | None = None) -> Any:
    client, _ = _client()
    with client:
        return _handle(client.patch(path, json=json))


def admin_put(path: str, *, json: dict | None = None) -> Any:
    client, _ = _client()
    with client:
        return _handle(client.put(path, json=json))


def admin_delete(path: str) -> None:
    client, _ = _client()
    with client:
        return _handle(client.delete(path))


def admin_upload(
    path: str,
    *,
    file_path: Path,
    fields: dict[str, str] | None = None,
    field_name: str = "file",
) -> Any:
    client, _ = _client()
    with client, file_path.open("rb") as fh:
        files = {field_name: (file_path.name, fh)}
        return _handle(client.post(path, files=files, data=fields or {}))
