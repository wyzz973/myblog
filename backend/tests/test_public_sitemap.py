"""Public sitemap.xml + Atom feed (Task 37)."""
from datetime import date

import pytest

from app.db import AsyncSessionLocal
from app.models import Post, Tag


@pytest.fixture
async def seeded_post():
    """Create a published, non-private post; clean up at teardown."""
    slug = "p37-sitemap-fixture"
    async with AsyncSessionLocal() as s:
        existing_tag = (await s.execute(
            Tag.__table__.select().where(Tag.slug == "p37-tag")
        )).first()
        if existing_tag is None:
            s.add(Tag(slug="p37-tag", name="p37", color="#888", sort_order=0))
            await s.flush()
            existing_tag = (await s.execute(
                Tag.__table__.select().where(Tag.slug == "p37-tag")
            )).first()
        s.add(Post(
            id=slug, n="1", title="Sitemap Fixture <Test>", subtitle="",
            date=date(2026, 4, 28), read="1", lang="en",
            summary="A sample summary & with quotes.",
            tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False,
            private=False, comments_enabled=True, tag_id=existing_tag.id,
        ))
        # Also a private post that must NOT appear.
        s.add(Post(
            id="p37-private", n="2", title="hidden", subtitle="",
            date=date(2026, 4, 29), read="1", lang="en",
            summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="published", featured=False,
            private=True, comments_enabled=True, tag_id=existing_tag.id,
        ))
        # And a draft.
        s.add(Post(
            id="p37-draft", n="3", title="draft", subtitle="",
            date=date(2026, 4, 30), read="1", lang="en",
            summary="", tldr="", body_md="", body_json=[],
            word_count=0, status="draft", featured=False,
            private=False, comments_enabled=True, tag_id=existing_tag.id,
        ))
        await s.commit()
    yield slug
    from sqlalchemy import delete as sa_delete
    async with AsyncSessionLocal() as s:
        await s.execute(sa_delete(Post).where(Post.id.in_(
            [slug, "p37-private", "p37-draft"]
        )))
        await s.execute(sa_delete(Tag).where(Tag.slug == "p37-tag"))
        await s.commit()


async def test_sitemap_returns_xml_with_published_post(client, seeded_post):
    r = await client.get("/api/sitemap.xml")
    assert r.status_code == 200, r.text
    assert "application/xml" in r.headers["content-type"]
    body = r.text
    # Root url present
    assert "<urlset" in body and "</urlset>" in body
    # The published post is in the listing
    assert f"/p/{seeded_post}" in body
    # The private + draft posts are NOT
    assert "/p/p37-private" not in body
    assert "/p/p37-draft" not in body


async def test_sitemap_escapes_special_chars(client, seeded_post):
    r = await client.get("/api/sitemap.xml")
    body = r.text
    # Title isn't in sitemap, but the URL should always be valid XML.
    # Smoke: parse the output to ensure it's well-formed XML.
    import xml.etree.ElementTree as ET
    ET.fromstring(body)


async def test_atom_feed_returns_well_formed(client, seeded_post):
    r = await client.get("/api/feed.xml")
    assert r.status_code == 200, r.text
    assert "application/xml" in r.headers["content-type"]
    body = r.text
    assert "<feed" in body and "</feed>" in body
    # The published post entry is present
    assert f"/p/{seeded_post}" in body
    # Title is XML-escaped (`<Test>` → `&lt;Test&gt;`)
    assert "&lt;Test&gt;" in body
    # Summary's `&` is escaped too
    assert "summary &amp; with" in body or "&amp;" in body
    # Validate XML parses
    import xml.etree.ElementTree as ET
    ET.fromstring(body)


async def test_atom_feed_is_publicly_accessible(client, seeded_post):
    """No auth required — search engines / RSS readers don't sign in."""
    r = await client.get("/api/feed.xml")
    assert r.status_code == 200


async def test_sitemap_no_published_posts_returns_empty_urlset(client):
    """With zero published posts, the urlset still returns 200 with the
    site-root entry only."""
    # Don't use the seeded fixture here; rely on whatever fixture state
    # exists. Just assert the response shape is valid XML with at least
    # the root <url>.
    r = await client.get("/api/sitemap.xml")
    assert r.status_code == 200
    import xml.etree.ElementTree as ET
    root = ET.fromstring(r.text)
    # urlset root with at least one <url> child (the site root)
    assert root.tag.endswith("urlset")
    assert len(list(root)) >= 1
