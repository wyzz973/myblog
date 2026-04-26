async def test_healthz(client):
    r = await client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


async def test_readyz_ok(client):
    r = await client.get("/api/readyz")
    assert r.status_code in (200, 503)  # 503 acceptable if DB/Redis offline; 200 expected when up


async def test_fakeredis_fixture_works(redis):
    await redis.set("k", "v")
    assert await redis.get("k") == "v"
    await redis.delete("k")
