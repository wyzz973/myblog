import pytest
from fastapi import Request
from starlette.datastructures import Headers

from app.services.client_ip import client_ip_from, client_ip_key_part


@pytest.fixture(autouse=True)
def _salt(monkeypatch):
    monkeypatch.setenv("LIKE_SALT", "test-salt-12345678")
    monkeypatch.delenv("TRUSTED_PROXIES", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()


def _mk_request(*, peer: str, headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "client": (peer, 0),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "method": "GET",
        "path": "/",
        "query_string": b"",
    }
    return Request(scope)


def test_no_proxy_returns_peer(monkeypatch):
    req = _mk_request(peer="1.2.3.4", headers={"x-forwarded-for": "5.6.7.8"})
    assert client_ip_from(req) == "1.2.3.4"


def test_trusted_proxy_uses_xff(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
    from app.config import get_settings
    get_settings.cache_clear()
    req = _mk_request(peer="10.0.0.1", headers={"x-forwarded-for": "9.9.9.9, 10.0.0.1"})
    assert client_ip_from(req) == "9.9.9.9"


def test_untrusted_peer_ignores_xff(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXIES", "10.0.0.1")
    from app.config import get_settings
    get_settings.cache_clear()
    req = _mk_request(peer="2.3.4.5", headers={"x-forwarded-for": "9.9.9.9"})
    assert client_ip_from(req) == "2.3.4.5"


def test_key_part_is_hashed():
    req = _mk_request(peer="1.2.3.4")
    part = client_ip_key_part(req)
    assert len(part) == 16
    assert "1.2.3.4" not in part
    assert "." not in part  # hex only
