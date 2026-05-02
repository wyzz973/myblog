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
