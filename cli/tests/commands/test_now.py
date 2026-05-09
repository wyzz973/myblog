import json as _json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_now_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/now").mock(
        return_value=httpx.Response(200, json=[{"id": 1, "kind": "reading", "label": "Book"}])
    )
    res = CliRunner().invoke(app, ["now", "list"])
    assert res.exit_code == 0
    assert "Book" in res.stdout


@respx.mock
def test_now_add(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.post("https://example.test/api/admin/now").mock(
        return_value=httpx.Response(201, json={"id": 2, "kind": "listening", "label": "song"})
    )
    res = CliRunner().invoke(app, ["now", "add", "--kind", "listening", "--label", "song"])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"kind": "listening", "label": "song"}


@respx.mock
def test_now_set(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.patch("https://example.test/api/admin/now/2").mock(
        return_value=httpx.Response(200, json={"id": 2, "label": "new"})
    )
    res = CliRunner().invoke(app, ["now", "set", "2", "--label", "new"])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"label": "new"}


@respx.mock
def test_now_rm(tmp_home) -> None:
    _seed(tmp_home)
    respx.delete("https://example.test/api/admin/now/2").mock(
        return_value=httpx.Response(204)
    )
    res = CliRunner().invoke(app, ["now", "rm", "2", "--yes"])
    assert res.exit_code == 0
