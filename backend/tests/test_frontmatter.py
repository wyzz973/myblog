from datetime import UTC, datetime

import pytest

from app.services.frontmatter_schema import PostFrontmatter


def _ok():
    return {
        "id": "termius-utf8", "n": "042", "title": "T", "tag": "devtools",
        "date": "2026-04-12", "lang": "zh",
    }


def test_minimal_valid():
    fm = PostFrontmatter(**_ok())
    assert fm.id == "termius-utf8"
    assert fm.status == "draft"
    assert fm.lang == "zh"
    assert fm.featured is False


def test_id_pattern():
    bad = _ok() | {"id": "Termius UTF8"}
    with pytest.raises(ValueError):
        PostFrontmatter(**bad)


def test_n_pattern():
    bad = _ok() | {"n": "42"}
    with pytest.raises(ValueError):
        PostFrontmatter(**bad)


def test_scheduled_requires_when():
    with pytest.raises(ValueError):
        PostFrontmatter(**(_ok() | {"status": "scheduled"}))


def test_scheduled_with_when():
    fm = PostFrontmatter(
        **(_ok() | {"status": "scheduled", "scheduled_at": datetime(2030, 1, 1, tzinfo=UTC)})
    )
    assert fm.status == "scheduled"


def test_lang_enum():
    with pytest.raises(ValueError):
        PostFrontmatter(**(_ok() | {"lang": "fr"}))
