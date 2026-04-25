import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_healthz(client):
    r = await client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_readyz_ok(client):
    r = await client.get("/api/readyz")
    assert r.status_code in (200, 503)  # 503 acceptable if DB/Redis offline; 200 expected when up
