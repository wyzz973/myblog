import json as _json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_tag_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g", "label": "general"}])
    )
    res = CliRunner().invoke(app, ["tag", "list"])
    assert res.exit_code == 0
    assert "general" in res.stdout


@respx.mock
def test_tag_add(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.post("https://example.test/api/admin/tags").mock(
        return_value=httpx.Response(201, json={"id": "g", "label": "General"})
    )
    res = CliRunner().invoke(app, ["tag", "add", "--id", "g", "--label", "General"])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"id": "g", "label": "General"}


@respx.mock
def test_tag_rename(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.patch("https://example.test/api/admin/tags/g").mock(
        return_value=httpx.Response(200, json={"id": "g", "label": "Notes"})
    )
    res = CliRunner().invoke(app, ["tag", "rename", "g", "--label", "Notes"])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"label": "Notes"}


@respx.mock
def test_tag_delete_dry_run(tmp_home) -> None:
    _seed(tmp_home)
    res = CliRunner().invoke(app, ["tag", "delete", "g"])
    assert res.exit_code == 1


@respx.mock
def test_tag_delete_yes(tmp_home) -> None:
    _seed(tmp_home)
    respx.delete("https://example.test/api/admin/tags/g").mock(
        return_value=httpx.Response(204)
    )
    res = CliRunner().invoke(app, ["tag", "delete", "g", "--yes"])
    assert res.exit_code == 0
