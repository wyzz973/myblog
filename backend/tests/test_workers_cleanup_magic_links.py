from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from app.db import AsyncSessionLocal
from app.models import MagicLink
from app.workers.tasks import cleanup_expired_magic_links


@pytest.fixture
async def seeded_links():
    async with AsyncSessionLocal() as s:
        await s.execute(delete(MagicLink))
        s.add_all([
            MagicLink(
                token_hash="a" * 64, account_id=1,
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
                created_at=datetime.now(UTC),
            ),
            MagicLink(
                token_hash="b" * 64, account_id=1,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                consumed_at=datetime.now(UTC),
                created_at=datetime.now(UTC),
            ),
            MagicLink(
                token_hash="c" * 64, account_id=1,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                created_at=datetime.now(UTC),
            ),
        ])
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(MagicLink))
        await s.commit()


async def test_cleanup_removes_expired_and_consumed(seeded_links):
    result = await cleanup_expired_magic_links({})
    assert result["count"] == 2

    async with AsyncSessionLocal() as s:
        survivors = (await s.execute(select(MagicLink))).scalars().all()
        assert len(survivors) == 1
        assert survivors[0].token_hash == "c" * 64
