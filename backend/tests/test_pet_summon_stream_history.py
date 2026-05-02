import json

import pytest

from app.services import pet_gateway


@pytest.fixture
def captured_streams(monkeypatch):
    """Capture all gateway.summon_stream calls and replay a fixed reply."""
    calls: list[dict] = []

    async def _fake_stream(**kwargs):
        calls.append(kwargs)
        yield {"type": "chunk", "text": "hello "}
        yield {"type": "chunk", "text": "world"}
        yield {"type": "done", "source": "zhipu"}

    monkeypatch.setattr(pet_gateway, "summon_stream", _fake_stream)
    return calls


async def _read_stream(client, payload):
    """POST and read all SSE frames; return list of parsed event dicts."""
    events = []
    async with client.stream(
        "POST", "/api/pet/summon/stream",
        json=payload,
        headers={"Content-Type": "application/json"},
    ) as r:
        assert r.status_code == 200
        buffer = ""
        async for chunk in r.aiter_text():
            buffer += chunk
            while "\n\n" in buffer:
                frame, buffer = buffer.split("\n\n", 1)
                for line in frame.split("\n"):
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
    return events


async def test_first_summon_with_no_history_sends_only_current_turn(
    client, captured_streams, fake_post_id,
):
    await _read_stream(client, {})
    assert len(captured_streams) == 1
    msgs = captured_streams[0]["messages"]
    assert len(msgs) == 1
    assert msgs[0]["role"] == "user"
    assert "tapped on you" in msgs[0]["content"]


async def test_second_summon_includes_first_turns_in_messages(
    client, captured_streams, fake_post_id,
):
    await _read_stream(client, {})
    await _read_stream(client, {})
    assert len(captured_streams) == 2
    msgs2 = captured_streams[1]["messages"]
    assert len(msgs2) == 3
    assert msgs2[0]["role"] == "user"
    assert "tapped on you" in msgs2[0]["content"]
    assert msgs2[1] == {"role": "assistant", "content": "hello world"}
    assert msgs2[2]["role"] == "user"


async def test_history_persists_to_pet_message_after_stream(
    client, captured_streams, fake_post_id,
):
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import PetMessage

    from app.services.pet_assignment import SPECIES_BY_RARITY

    valid_species = {s for pool in SPECIES_BY_RARITY.values() for s in pool}

    await _read_stream(client, {"post_id": fake_post_id})
    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetMessage))).scalars().all()
        assert len(rows) >= 1
        latest = max(rows, key=lambda r: r.created_at)
        # Species is determined by visitor fingerprint (ip+ua), so we
        # can't assert a specific value, only that it's in the catalog.
        assert latest.species in valid_species
        assert latest.mode in ("greet", "summary_react")
        assert latest.reply == "hello world"
        assert latest.source == "zhipu"
        # Cleanup
        for r in rows:
            await s.delete(r)
        await s.commit()


async def test_stream_fallback_archive_matches_visible_fallback(
    client, monkeypatch,
):
    from sqlalchemy import select
    from app.db import AsyncSessionLocal
    from app.models import PetMessage
    from app.services import pet_gateway

    async def _fallback_stream(**kwargs):
        yield {"type": "fallback", "text": "same fallback", "source": "fallback"}

    monkeypatch.setattr(pet_gateway, "summon_stream", _fallback_stream)

    events = await _read_stream(client, {})
    assert {"type": "fallback", "text": "same fallback", "source": "fallback"} in events

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(PetMessage))).scalars().all()
        latest = max(rows, key=lambda r: r.created_at)
        assert latest.reply == "same fallback"
        assert latest.source == "fallback"
        for r in rows:
            await s.delete(r)
        await s.commit()


@pytest.fixture
async def reset_redis_state(redis):
    """Clear pet:ctx:* + rl:pet:* keys to isolate this test."""
    for pattern in ("pet:ctx:*", "rl:pet:*"):
        keys = await redis.keys(pattern)
        for k in keys:
            await redis.delete(k)
    yield
    for pattern in ("pet:ctx:*", "rl:pet:*"):
        keys = await redis.keys(pattern)
        for k in keys:
            await redis.delete(k)


async def test_rate_limited_does_not_pollute_history(
    client, captured_streams, fake_post_id, redis, reset_redis_state,
):
    """A rate-limited canned reply must NOT enter Redis ctx so the
    next successful summon doesn't see 'pets 累了' in messages."""
    from sqlalchemy import update
    from app.db import AsyncSessionLocal
    from app.models import SiteMeta
    from app.schemas.pet import PetConfig

    # Tighten rate limit so the second call breaches.
    cfg = PetConfig(per_ip_per_min=1, per_ip_per_day=99, global_per_day=99)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1)
                        .values(pet_config=cfg.model_dump()))
        await s.commit()

    # First call: ok (gateway captured)
    await _read_stream(client, {})
    # Second call: rate limited (gateway NOT captured)
    events2 = await _read_stream(client, {})
    rl = [e for e in events2 if e.get("type") == "rate_limited"]
    assert rl, f"expected rate_limited event, got {events2}"
    assert len(captured_streams) == 1, "gateway should be skipped on rate limit"

    # Reset to defaults + clear rl counters; third call should NOT see canned reply in history.
    cfg2 = PetConfig()
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1)
                        .values(pet_config=cfg2.model_dump()))
        await s.commit()
    keys = await redis.keys("rl:pet:*")
    for k in keys:
        await redis.delete(k)

    await _read_stream(client, {})
    msgs3 = captured_streams[1]["messages"]
    # 3 messages = first ok user + first ok assistant + current user.
    # Rate-limited canned line MUST be absent.
    assert len(msgs3) == 3
    contents = [m["content"] for m in msgs3]
    for c in contents[:-1]:
        assert "累了" not in c
        assert "nap" not in c.lower()
