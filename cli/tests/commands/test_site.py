import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_site_get_human(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/site").mock(
        return_value=httpx.Response(200, json={"handle": "wyz", "tagline": "hi"})
    )
    res = CliRunner().invoke(app, ["site", "get"])
    assert res.exit_code == 0
    assert "wyz" in res.stdout


@respx.mock
def test_site_set_sends_only_provided_fields(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.put("https://example.test/api/admin/site").mock(
        return_value=httpx.Response(200, json={"handle": "wyz", "tagline": "new"})
    )
    res = CliRunner().invoke(app, ["site", "set", "--tagline", "new"])
    assert res.exit_code == 0
    import json as _json
    assert _json.loads(route.calls.last.request.read()) == {"tagline": "new"}


@respx.mock
def test_site_theme_set(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.put("https://example.test/api/admin/theme").mock(
        return_value=httpx.Response(200, json={"accent_color": "#abc"})
    )
    res = CliRunner().invoke(app, ["site", "theme", "set", "--accent", "#abc"])
    assert res.exit_code == 0
    import json as _json
    assert _json.loads(route.calls.last.request.read()) == {"accent_color": "#abc"}
