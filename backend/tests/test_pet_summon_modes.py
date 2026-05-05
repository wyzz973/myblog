import pytest
from sqlalchemy import update

from app.db import engine
from app.models import SiteMeta
from app.services import pet_gateway


@pytest.fixture(autouse=True)
async def reset_pet_config(request):
    """Reset pet_config to defaults before each test that hits HTTP endpoints.

    Mirrors the fixture in test_pet_summon.py — a couple of tests below mutate
    pet_config (e.g. enable_article_context=False) and we don't want that
    bleeding into other test modules that run alphabetically after this one.
    """
    if "client" not in request.fixturenames:
        yield
        return
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.schemas.pet import PetConfig

    defaults = PetConfig().model_dump()
    async with AsyncSession(engine) as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=defaults))
        await s.commit()
    yield


@pytest.fixture
def captured_calls(monkeypatch):
    calls: list[dict] = []

    async def _fake_summon(**kwargs):
        calls.append(kwargs)
        return ("ok", "zhipu")

    monkeypatch.setattr(pet_gateway, "summon", _fake_summon)
    return calls


async def test_greet_mode_when_no_post_no_selection(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "greet"
    assert "tapped on you" in captured_calls[0]["system"]


async def test_summary_react_mode_with_post(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={"post_id": fake_post_id})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "summary_react"
    sys = captured_calls[0]["system"]
    assert "Pet Test" in sys      # title
    assert "devtools" in sys      # tag


async def test_selection_explain_when_explicit_flag(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "useEffect(() => fetch(url), [])",
        "mode": "selection_explain",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "selection_explain"
    assert "useEffect" in captured_calls[0]["system"]
    assert "Explain what this snippet" in captured_calls[0]["system"]


async def test_selection_qa_default_when_selection_no_mode(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "this is a paragraph",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "selection_qa"


async def test_free_chat_inferred_when_message_without_mode(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "message": "这篇文章最关键的风险是什么？",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "free_chat"
    assert "这篇文章最关键的风险是什么" in captured_calls[0]["user"]


async def test_short_follow_up_inferred_from_message(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "message": "继续",
    })
    assert r.status_code == 200
    assert r.json()["mode"] == "follow_up"


async def test_code_assist_explicit_mode_accepts_client_context(client, captured_calls, fake_post_id):
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "useEffect(() => {}, [])",
        "mode": "code_assist",
        "client_context": {
            "page_type": "post",
            "visible_block_type": "code",
            "selection_kind": "code",
            "dwell_seconds": 25,
        },
    })
    assert r.status_code == 200
    assert r.json()["mode"] == "code_assist"
    assert "Help with a code-oriented moment" in captured_calls[0]["system"]


async def test_free_chat_can_be_disabled_without_provider_call(client, captured_calls):
    from sqlalchemy import update

    from app.db import AsyncSessionLocal
    from app.models import SiteMeta
    from app.schemas.pet import PetConfig

    cfg = PetConfig(enable_free_chat=False)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1).values(pet_config=cfg.model_dump()))
        await s.commit()

    r = await client.post("/api/pet/summon", json={"message": "hello"})
    assert r.status_code == 200
    assert r.json()["source"] == "disabled"
    assert captured_calls == []


async def test_mode_validation_rejects_garbage(client, captured_calls):
    r = await client.post("/api/pet/summon", json={"mode": "wat"})
    assert r.status_code == 422


async def test_disabled_article_context_forces_greet_mode(client, captured_calls,
                                                          fake_post_id):
    """When enable_article_context=False, ignore post_id/selection, force greet."""
    from sqlalchemy import update

    from app.db import AsyncSessionLocal
    from app.models import SiteMeta
    from app.schemas.pet import PetConfig
    cfg = PetConfig(enable_article_context=False)
    async with AsyncSessionLocal() as s:
        await s.execute(update(SiteMeta).where(SiteMeta.id == 1)
                        .values(pet_config=cfg.model_dump()))
        await s.commit()
    r = await client.post("/api/pet/summon", json={
        "post_id": fake_post_id,
        "selection": "x",
    })
    body = r.json()
    assert body["mode"] == "greet"
    sys = captured_calls[0]["system"]
    assert "Pet Test" not in sys  # title NOT injected
