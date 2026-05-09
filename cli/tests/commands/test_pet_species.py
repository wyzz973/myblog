import json as _json

import httpx
import respx
from typer.testing import CliRunner

from myblog import config
from myblog.__main__ import app


def _seed(tmp_home):
    config.save_credentials(base_url="https://example.test", admin_token="t")


@respx.mock
def test_species_list(tmp_home) -> None:
    _seed(tmp_home)
    respx.get("https://example.test/api/admin/pet/species").mock(
        return_value=httpx.Response(200, json=[{"id": "cat", "name": "Cat", "color": "#aaa"}])
    )
    res = CliRunner().invoke(app, ["pet", "species", "list"])
    assert res.exit_code == 0
    assert "cat" in res.stdout


@respx.mock
def test_species_add_from_json(tmp_home, tmp_path) -> None:
    _seed(tmp_home)
    payload = {"id": "fox", "name": "Fox", "color": "#f60", "sort_order": 9, "visible": True}
    f = tmp_path / "fox.json"
    f.write_text(_json.dumps(payload))
    route = respx.post("https://example.test/api/admin/pet/species").mock(
        return_value=httpx.Response(201, json=payload)
    )
    res = CliRunner().invoke(app, ["pet", "species", "add", "--from-json", str(f)])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == payload


@respx.mock
def test_species_edit_from_json(tmp_home, tmp_path) -> None:
    _seed(tmp_home)
    f = tmp_path / "patch.json"
    f.write_text(_json.dumps({"name": "Foxy"}))
    route = respx.patch("https://example.test/api/admin/pet/species/fox").mock(
        return_value=httpx.Response(200, json={"id": "fox", "name": "Foxy"})
    )
    res = CliRunner().invoke(app, ["pet", "species", "edit", "fox", "--from-json", str(f)])
    assert res.exit_code == 0
    assert _json.loads(route.calls.last.request.read()) == {"name": "Foxy"}


@respx.mock
def test_species_rm_dry_run(tmp_home) -> None:
    _seed(tmp_home)
    res = CliRunner().invoke(app, ["pet", "species", "rm", "fox"])
    assert res.exit_code == 1


@respx.mock
def test_species_rm_yes(tmp_home) -> None:
    _seed(tmp_home)
    respx.delete("https://example.test/api/admin/pet/species/fox").mock(
        return_value=httpx.Response(204)
    )
    res = CliRunner().invoke(app, ["pet", "species", "rm", "fox", "--yes"])
    assert res.exit_code == 0
