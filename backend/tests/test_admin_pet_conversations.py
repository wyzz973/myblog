from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models import PetMessage

EMAIL = "hi@wangyang.dev"
PASS = "changeme"


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


@pytest.fixture
async def admin_token(client):
    r = await client.post("/api/admin/auth/login", json={"email": EMAIL, "password": PASS})
    return r.json()["access"]


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seed_pet_messages():
    """Insert 5 pet_message rows across 3 visitors. Yield, then cleanup."""
    now = datetime.now(UTC)
    async with AsyncSession(engine) as s:
        rows = [
            PetMessage(
                visitor_hash="alice000000000aa",
                species="cat", mode="greet",
                system_prompt="x", prior_turns=[],
                reply="alice-1", source="zhipu",
                created_at=now - timedelta(minutes=30),
            ),
            PetMessage(
                visitor_hash="alice000000000aa",
                species="cat", mode="summary_react",
                system_prompt="x", prior_turns=[],
                reply="alice-2", source="zhipu",
                created_at=now - timedelta(minutes=10),
            ),
            PetMessage(
                visitor_hash="bob000000000000b",
                species="dragon", mode="greet",
                system_prompt="x", prior_turns=[],
                reply="bob-1", source="anthropic",
                created_at=now - timedelta(minutes=20),
            ),
            PetMessage(
                visitor_hash="bob000000000000b",
                species="dragon", mode="selection_qa",
                system_prompt="x", prior_turns=[],
                reply="bob-2", source="anthropic",
                created_at=now - timedelta(minutes=5),
            ),
            PetMessage(
                visitor_hash="carol00000000000",
                species="fox", mode="greet",
                system_prompt="x", prior_turns=[],
                reply="carol-1", source="zhipu",
                created_at=now - timedelta(hours=2),
            ),
        ]
        for r in rows:
            s.add(r)
        await s.commit()
        yield rows
        # Cleanup
        for r in rows:
            await s.delete(r)
        await s.commit()


async def test_get_conversations_groups_by_visitor_hash(
    client, admin_token, seed_pet_messages,
):
    r = await client.get("/api/admin/pet/conversations", headers=_hdr(admin_token))
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    by_hash = {it["visitor_hash"]: it for it in items}
    assert "alice000000000aa" in by_hash
    assert "bob000000000000b" in by_hash
    assert "carol00000000000" in by_hash
    assert by_hash["alice000000000aa"]["message_count"] == 2
    assert by_hash["bob000000000000b"]["message_count"] == 2
    assert by_hash["carol00000000000"]["message_count"] == 1
    assert by_hash["alice000000000aa"]["species"] == "cat"
    assert "alice-2" in by_hash["alice000000000aa"]["last_reply_preview"]


async def test_conversations_ordered_by_last_msg_desc(
    client, admin_token, seed_pet_messages,
):
    r = await client.get("/api/admin/pet/conversations", headers=_hdr(admin_token))
    items = r.json()["items"]
    seeded_in_order = [it for it in items
                        if it["visitor_hash"] in
                        {"alice000000000aa", "bob000000000000b", "carol00000000000"}]
    hashes = [it["visitor_hash"] for it in seeded_in_order]
    assert hashes == ["bob000000000000b", "alice000000000aa", "carol00000000000"]


async def test_conversations_filter_by_species(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations?species=dragon",
        headers=_hdr(admin_token),
    )
    items = r.json()["items"]
    seeded = [it for it in items
              if it["visitor_hash"] in
              {"alice000000000aa", "bob000000000000b", "carol00000000000"}]
    assert all(it["species"] == "dragon" for it in seeded)
    assert any(it["visitor_hash"] == "bob000000000000b" for it in seeded)


async def test_conversations_pagination(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations?limit=2",
        headers=_hdr(admin_token),
    )
    body = r.json()
    assert len(body["items"]) <= 2
    if body.get("next_cursor"):
        r2 = await client.get(
            f"/api/admin/pet/conversations?limit=2&cursor={body['next_cursor']}",
            headers=_hdr(admin_token),
        )
        first_hashes = {it["visitor_hash"] for it in body["items"]}
        for it in r2.json()["items"]:
            assert it["visitor_hash"] not in first_hashes


async def test_conversations_requires_auth(client):
    r = await client.get("/api/admin/pet/conversations")
    assert r.status_code == 401


async def test_get_conversation_detail_returns_messages_oldest_first(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations/alice000000000aa",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    body = r.json()
    items = body["items"]
    assert len(items) == 2
    # Oldest first
    assert items[0]["reply"] == "alice-1"
    assert items[1]["reply"] == "alice-2"
    # Includes archive metadata
    assert "system_prompt" in items[0]
    assert "prior_turns" in items[0]


async def test_get_conversation_detail_pagination(
    client, admin_token, seed_pet_messages,
):
    r = await client.get(
        "/api/admin/pet/conversations/alice000000000aa?limit=1",
        headers=_hdr(admin_token),
    )
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["reply"] == "alice-1"
    assert body.get("next_cursor")


async def test_get_conversation_detail_unknown_visitor_empty(
    client, admin_token,
):
    r = await client.get(
        "/api/admin/pet/conversations/nonexistent",
        headers=_hdr(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["items"] == []
