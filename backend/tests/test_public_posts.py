"""Tests for `/api/posts` list / filter / pagination.

The seeded dev DB ships with 14 posts in `draft` status, all `lang=en`. To
exercise the published-only and `lang=zh` paths, this module flips a small
deterministic subset to `published` (and one to `lang=zh`) before running.
The mutations are kept in place — the dev DB is not the source of truth for
production state.
"""
import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Post


@pytest.fixture(scope="module", autouse=True)
async def _publish_a_few_posts():
    """Flip a deterministic subset of seeded posts to published so the public
    list endpoint has rows to return in tests. Sets one post to `lang=zh` so
    the lang filter assertion has a non-empty hit too.

    Uses a dedicated short-lived engine that gets disposed before any tests
    run; this avoids stashing connections in the shared `app.db.engine` pool
    that get reused by per-test ASGI clients running on a different event
    loop. Idempotent — re-running the same UPDATEs is harmless.
    """
    settings = get_settings()
    eng = create_async_engine(settings.database_url, future=True)
    Session = async_sessionmaker(eng, expire_on_commit=False)
    async with Session() as s:
        await s.execute(
            update(Post)
            .where(Post.id.in_(["termius-utf8", "pagehelper", "baidu-comate"]))
            .values(status="published")
        )
        await s.execute(
            update(Post)
            .where(Post.id == "baidu-comate")
            .values(lang="zh")
        )
        await s.commit()
    await eng.dispose()
    yield


async def test_posts_list_returns_paged(client):
    r = await client.get("/api/posts?limit=20&offset=0")
    assert r.status_code == 200
    body = r.json()
    assert {"items", "total", "limit", "offset"} <= set(body.keys())
    assert body["limit"] == 20
    assert body["offset"] == 0


async def test_posts_list_filter_by_tag(client):
    r = await client.get("/api/posts?tag=devtools")
    assert r.status_code == 200
    body = r.json()
    for p in body["items"]:
        assert p["tag"] == "devtools"


async def test_posts_list_search_query(client):
    r = await client.get("/api/posts?q=Termius")
    assert r.status_code == 200
    body = r.json()
    assert all("Termius" in p["title"] or "Termius" in (p["summary"] or "") for p in body["items"])


async def test_posts_list_lang_filter(client):
    r = await client.get("/api/posts?lang=zh")
    assert r.status_code == 200
    for p in r.json()["items"]:
        assert p["lang"] == "zh"


async def test_posts_list_excludes_drafts(client):
    r = await client.get("/api/posts")
    assert all(p.get("status", "published") == "published" for p in r.json()["items"])
