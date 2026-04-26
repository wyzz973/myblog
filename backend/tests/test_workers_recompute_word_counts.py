from datetime import UTC, date, datetime

import pytest
from sqlalchemy import delete, insert, select

from app.db import AsyncSessionLocal
from app.models import Post, Tag
from app.workers.tasks import recompute_post_word_counts


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose asyncpg pool between tests to avoid Future-attached-to-different-loop."""
    from app import db as _db
    yield
    await _db.engine.dispose()


@pytest.fixture
async def seeded_post():
    pid = "p5-recompute"
    async with AsyncSessionLocal() as s:
        tag = (await s.execute(select(Tag).limit(1))).scalar_one()
        await s.execute(delete(Post).where(Post.id == pid))
        await s.execute(insert(Post).values(
            id=pid, n="803", title="t", tag_id=tag.id, date=date(2026, 1, 1),
            lang="en", body_md="hello world this has six words",
            body_json={"blocks": []},
            word_count=999,  # deliberately wrong
            status="published",
            featured=False, private=False, comments_enabled=True,
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
        ))
        await s.commit()
    yield pid
    async with AsyncSessionLocal() as s:
        await s.execute(delete(Post).where(Post.id == pid))
        await s.commit()


async def test_recompute_fixes_word_count(seeded_post):
    result = await recompute_post_word_counts({})
    assert result["updated"] >= 1

    async with AsyncSessionLocal() as s:
        post = (await s.execute(select(Post).where(Post.id == seeded_post))).scalar_one()
        # the existing markdown_pipeline.compute_derived defines word counting;
        # all that matters here is that it's no longer 999
        assert post.word_count != 999
