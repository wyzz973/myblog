from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models import PetMessage


@pytest.fixture(autouse=True)
async def _reset_pool():
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


async def test_insert_pet_message_basic_roundtrip():
    async with AsyncSession(engine) as s:
        m = PetMessage(
            visitor_hash="abc123def456",
            species="cat",
            mode="greet",
            post_id=None,
            title=None,
            tag_slug=None,
            summary=None,
            selection=None,
            system_prompt="you are cat",
            prior_turns=[],
            reply="meow",
            source="zhipu",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        assert m.id is not None
        assert isinstance(m.created_at, datetime)
        assert m.created_at.tzinfo is not None  # DateTime(timezone=True)
        # Cleanup
        await s.delete(m)
        await s.commit()


async def test_prior_turns_jsonb_roundtrip():
    async with AsyncSession(engine) as s:
        prior = [
            {"role": "user", "content": "hi", "mode": "greet", "post_id": None},
            {"role": "assistant", "content": "hello there", "mode": "greet", "post_id": None},
        ]
        m = PetMessage(
            visitor_hash="abc",
            species="cat",
            mode="summary_react",
            post_id="hello",
            title="Hello",
            tag_slug="devtools",
            summary="An article",
            selection=None,
            system_prompt="...",
            prior_turns=prior,
            reply="hi back",
            source="anthropic",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        assert m.prior_turns == prior
        await s.delete(m)
        await s.commit()


async def test_selection_can_be_null():
    async with AsyncSession(engine) as s:
        m = PetMessage(
            visitor_hash="x",
            species="cat",
            mode="greet",
            system_prompt="x",
            prior_turns=[],
            reply="x",
            source="fallback",
        )
        s.add(m)
        await s.commit()
        await s.refresh(m)
        assert m.selection is None
        await s.delete(m)
        await s.commit()
