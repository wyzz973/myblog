import json as _json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_pet_config_get(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/pet").mock(
        return_value=httpx.Response(200, json={"enabled": True, "personas": {}, "mode_templates": {}})
    )
    res = CliRunner().invoke(app, ["pet", "config", "get"])
    assert res.exit_code == 0
    assert "enabled" in res.stdout


@respx.mock
def test_pet_config_set_from_json(tmp_home, tmp_path) -> None:
    _seed(tmp_home)
    cfg_in = {"enabled": False, "personas": {}, "mode_templates": {}}
    f = tmp_path / "cfg.json"
    f.write_text(_json.dumps(cfg_in))
    route = respx.put("https://example.test/api/admin/pet").mock(
        return_value=httpx.Response(200, json=cfg_in)
    )
    res = CliRunner().invoke(app, ["pet", "config", "set", "--from-json", str(f)])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == cfg_in


@respx.mock
def test_pet_personality_get_returns_slice(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/pet").mock(
        return_value=httpx.Response(200, json={
            "enabled": True,
            "personas": {"chill": "..."},
            "mode_templates": {"hint": "..."},
            "irrelevant": "skip",
        })
    )
    res = CliRunner().invoke(app, ["--json", "pet", "personality", "get"])
    assert res.exit_code == 0
    obj = _json.loads(res.stdout.splitlines()[0])
    assert "personas" in obj and "mode_templates" in obj
    assert "irrelevant" not in obj


@respx.mock
def test_pet_personality_reset_personas(tmp_home) -> None:
    _seed(tmp_home)
    route = respx.post("https://example.test/api/admin/pet/reset", params={"section": "personas"}).mock(
        return_value=httpx.Response(200, json={"enabled": True})
    )
    res = CliRunner().invoke(app, ["pet", "personality", "reset", "personas", "--yes"])
    assert res.exit_code == 0
    assert route.called


@respx.mock
def test_pet_memory_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/pet/conversations").mock(
        return_value=httpx.Response(200, json={
            "items": [{"visitor_hash": "abc", "msg_count": 3, "last_at": "2026-05-09"}],
            "next_cursor": None,
        })
    )
    res = CliRunner().invoke(app, ["pet", "memory", "list"])
    assert res.exit_code == 0
    assert "abc" in res.stdout
