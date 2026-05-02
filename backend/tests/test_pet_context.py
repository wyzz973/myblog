import pytest
import fakeredis.aioredis

from app.services.pet_context import (
    DEFAULT_MAX_TURNS,
    DEFAULT_TTL_SEC,
    KEY_PREFIX,
    append,
    clear,
    load,
)


@pytest.fixture
async def redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        yield r
    finally:
        await r.aclose()


async def test_load_returns_empty_when_no_history(redis):
    assert await load(redis, "v1") == []


async def test_append_then_load_returns_chronological_pair(redis):
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "hi"},
        assistant_turn={"role": "assistant", "content": "hello"},
    )
    out = await load(redis, "v1")
    assert out == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


async def test_multiple_appends_keep_chronological_order(redis):
    for i in range(3):
        await append(
            redis, "v1",
            user_turn={"role": "user", "content": f"u{i}"},
            assistant_turn={"role": "assistant", "content": f"a{i}"},
        )
    out = await load(redis, "v1")
    contents = [t["content"] for t in out]
    assert contents == ["u0", "a0", "u1", "a1", "u2", "a2"]


async def test_append_caps_at_2x_max_turns(redis):
    for i in range(15):
        await append(
            redis, "v1",
            user_turn={"role": "user", "content": f"u{i}"},
            assistant_turn={"role": "assistant", "content": f"a{i}"},
            max_turns=5,
        )
    out = await load(redis, "v1", max_turns=5)
    assert len(out) == 10  # 5 pairs
    contents = [t["content"] for t in out]
    # Most recent 5 pairs, chronological
    assert contents == ["u10", "a10", "u11", "a11", "u12", "a12", "u13", "a13", "u14", "a14"]


async def test_load_with_smaller_max_turns_truncates(redis):
    for i in range(5):
        await append(
            redis, "v1",
            user_turn={"role": "user", "content": f"u{i}"},
            assistant_turn={"role": "assistant", "content": f"a{i}"},
        )
    out = await load(redis, "v1", max_turns=2)
    assert len(out) == 4
    contents = [t["content"] for t in out]
    assert contents == ["u3", "a3", "u4", "a4"]


async def test_append_resets_ttl_each_call(redis):
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "a"},
        assistant_turn={"role": "assistant", "content": "b"},
        ttl_sec=100,
    )
    ttl1 = await redis.ttl(f"{KEY_PREFIX}v1")
    assert 90 <= ttl1 <= 100
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "c"},
        assistant_turn={"role": "assistant", "content": "d"},
        ttl_sec=300,
    )
    ttl2 = await redis.ttl(f"{KEY_PREFIX}v1")
    assert 290 <= ttl2 <= 300


async def test_clear_deletes_key(redis):
    await append(
        redis, "v1",
        user_turn={"role": "user", "content": "a"},
        assistant_turn={"role": "assistant", "content": "b"},
    )
    await clear(redis, "v1")
    assert await load(redis, "v1") == []


async def test_default_constants():
    assert DEFAULT_MAX_TURNS == 10
    assert DEFAULT_TTL_SEC == 7200
