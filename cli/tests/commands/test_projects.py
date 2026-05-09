import json as _json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_projects_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/projects").mock(
        return_value=httpx.Response(200, json=[{"name": "myblog", "url": "https://x"}])
    )
    res = CliRunner().invoke(app, ["projects", "list"])
    assert res.exit_code == 0
    assert "myblog" in res.stdout


@respx.mock
def test_projects_add_from_json(tmp_home, tmp_path) -> None:
    _seed(tmp_home)
    p = {"name": "myblog", "url": "https://wyz", "blurb": "hi"}
    f = tmp_path / "p.json"
    f.write_text(_json.dumps(p))
    route = respx.post("https://example.test/api/admin/projects").mock(
        return_value=httpx.Response(201, json=p)
    )
    res = CliRunner().invoke(app, ["projects", "add", "--from-json", str(f)])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == p


@respx.mock
def test_projects_set_field(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.patch("https://example.test/api/admin/projects/myblog").mock(
        return_value=httpx.Response(200, json={"name": "myblog", "blurb": "new"})
    )
    res = CliRunner().invoke(app, ["projects", "set", "myblog", "--blurb", "new"])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"blurb": "new"}
