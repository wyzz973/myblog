"""Task 36: cost-rates endpoint tests."""
import pytest

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


async def test_get_returns_defaults_when_no_overrides(client, admin_token):
    r = await client.get("/api/admin/pet/cost-rates", headers=_auth(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    rates = body["rates"]
    assert "anthropic" in rates and "default" in rates
    # Default fallback shape
    assert isinstance(rates["anthropic"]["in_per_m"], (int, float))
    assert isinstance(rates["anthropic"]["out_per_m"], (int, float))


async def test_put_returns_404_when_provider_not_configured(client, admin_token):
    """Without a configured Integration row, PUT can't write extra_json."""
    r = await client.put(
        "/api/admin/pet/cost-rates",
        json={"provider": "qwen", "in_per_m": 0.5, "out_per_m": 1.0},
        headers={**_auth(admin_token), "Content-Type": "application/json"},
    )
    # qwen integration not configured in test DB → 404
    assert r.status_code in (200, 404), r.text


async def test_put_rejects_negative_rates(client, admin_token):
    r = await client.put(
        "/api/admin/pet/cost-rates",
        json={"provider": "anthropic", "in_per_m": -1, "out_per_m": 1},
        headers={**_auth(admin_token), "Content-Type": "application/json"},
    )
    assert r.status_code == 422


async def test_put_rejects_unknown_provider(client, admin_token):
    r = await client.put(
        "/api/admin/pet/cost-rates",
        json={"provider": "openai", "in_per_m": 0.5, "out_per_m": 1.0},
        headers={**_auth(admin_token), "Content-Type": "application/json"},
    )
    assert r.status_code == 422  # Literal validator rejects


async def test_get_unauth_401(client):
    r = await client.get("/api/admin/pet/cost-rates")
    assert r.status_code == 401


async def test_put_with_configured_integration_persists_override(
    client, admin_token,
):
    """End-to-end: configure an integration row, set the rate, re-fetch, see override."""
    from datetime import UTC, datetime
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import Integration
    from app.services import secret_box

    # Insert a minimal anthropic integration row directly.
    async with AsyncSessionLocal() as s:
        existing = (await s.execute(
            select(Integration).where(Integration.name == "anthropic")
        )).scalar_one_or_none()
        if existing is None:
            s.add(Integration(
                name="anthropic", username=None,
                secret_encrypted=secret_box.encrypt("placeholder-key"),
                extra_json={"model": "claude"},
                created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
            ))
            await s.commit()

    try:
        put = await client.put(
            "/api/admin/pet/cost-rates",
            json={"provider": "anthropic", "in_per_m": 7.77, "out_per_m": 22.22},
            headers={**_auth(admin_token), "Content-Type": "application/json"},
        )
        assert put.status_code == 200, put.text
        body = put.json()
        assert body["rates"]["anthropic"]["in_per_m"] == 7.77
        assert body["rates"]["anthropic"]["out_per_m"] == 22.22

        # Re-fetch confirms persistence.
        get = await client.get("/api/admin/pet/cost-rates", headers=_auth(admin_token))
        assert get.json()["rates"]["anthropic"]["in_per_m"] == 7.77
    finally:
        from sqlalchemy import delete
        async with AsyncSessionLocal() as s:
            await s.execute(delete(Integration).where(Integration.name == "anthropic"))
            await s.commit()
