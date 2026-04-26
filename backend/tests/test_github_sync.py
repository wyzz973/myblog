"""Mock GraphQL responses; service must hit the right query and parse correctly."""
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.github import fetch_contributions, ping


@pytest.fixture(autouse=True)
async def _reset_pool():
    """Dispose the engine pool before each test so asyncpg connections are
    not carried across test-local event loops."""
    from app import db as _db
    await _db.engine.dispose()
    yield
    await _db.engine.dispose()


CONTRIBUTIONS_FAKE = {
    "data": {
        "user": {
            "contributionsCollection": {
                "contributionCalendar": {
                    "weeks": [
                        {"contributionDays": [
                            {"date": "2026-04-20", "contributionCount": 5},
                            {"date": "2026-04-21", "contributionCount": 0},
                        ]},
                        {"contributionDays": [
                            {"date": "2026-04-22", "contributionCount": 12},
                        ]},
                    ]
                }
            }
        }
    }
}


VIEWER_FAKE = {"data": {"viewer": {"login": "myuser"}}}


def _mock_post(payload: dict, status: int = 200):
    async def _post(self, url, json=None, headers=None, timeout=None):
        return httpx.Response(status, json=payload, request=httpx.Request("POST", url))
    return _post


async def test_ping_success():
    with patch("httpx.AsyncClient.post", new=_mock_post(VIEWER_FAKE)):
        login = await ping("ghp_token")
        assert login == "myuser"


async def test_ping_unauthorized():
    with patch("httpx.AsyncClient.post", new=_mock_post({"errors": [{"message": "Bad creds"}]}, status=401)):
        login = await ping("ghp_bad")
        assert login is None


async def test_fetch_contributions_parses_days():
    with patch("httpx.AsyncClient.post", new=_mock_post(CONTRIBUTIONS_FAKE)):
        days = await fetch_contributions("ghp_token", "myuser")
        assert len(days) == 3
        assert days[0]["day"] == date(2026, 4, 20)
        assert days[0]["count"] == 5
        # level: count=5 → bucket 4-9 (level 2 in 0-4 scale)
        assert days[0]["level"] == 2
        assert days[1]["count"] == 0
        assert days[1]["level"] == 0
        assert days[2]["count"] == 12
        assert days[2]["level"] == 3


async def test_fetch_contributions_empty_user():
    payload = {"data": {"user": None}}
    with patch("httpx.AsyncClient.post", new=_mock_post(payload, status=200)):
        days = await fetch_contributions("ghp_token", "ghost")
        assert days == []


async def test_sync_github_contrib_upserts_contrib_days(monkeypatch):
    from datetime import UTC, datetime as dt
    from sqlalchemy import delete, select
    from app.db import AsyncSessionLocal
    from app.models import ContribDay, Integration
    from app.services import integrations
    from app.workers.tasks import sync_github_contrib

    monkeypatch.setenv("LIKE_SALT", "x" * 32)
    from app.config import get_settings
    get_settings.cache_clear()

    async with AsyncSessionLocal() as s:
        await s.execute(delete(ContribDay))
        await s.execute(delete(Integration).where(Integration.name == "github"))
        await integrations.upsert(s, name="github", username="myuser", secret="ghp_token")
        await s.commit()

    from unittest.mock import patch
    with patch("app.services.github.fetch_contributions") as fetch:
        fetch.return_value = [
            {"day": dt(2026, 1, 1).date(), "count": 5, "level": 2},
            {"day": dt(2026, 1, 2).date(), "count": 0, "level": 0},
        ]
        result = await sync_github_contrib({})

    assert result["count"] == 2

    async with AsyncSessionLocal() as s:
        rows = (await s.execute(select(ContribDay))).scalars().all()
        assert len(rows) == 2
        row = (await s.execute(select(Integration).where(Integration.name == "github"))).scalar_one()
        assert row.last_status == "ok"

        # cleanup
        await s.execute(delete(ContribDay))
        await s.execute(delete(Integration).where(Integration.name == "github"))
        await s.commit()


async def test_sync_github_contrib_marks_failure(monkeypatch):
    from sqlalchemy import delete, select
    from app.db import AsyncSessionLocal
    from app.models import Integration
    from app.services import integrations
    from app.workers.tasks import sync_github_contrib

    async with AsyncSessionLocal() as s:
        await s.execute(delete(Integration).where(Integration.name == "github"))
        await integrations.upsert(s, name="github", username="myuser", secret="ghp_bad")
        await s.commit()

    from unittest.mock import patch
    with patch("app.services.github.fetch_contributions", side_effect=ConnectionError("network")):
        with pytest.raises(ConnectionError):
            await sync_github_contrib({})

    async with AsyncSessionLocal() as s:
        row = (await s.execute(select(Integration).where(Integration.name == "github"))).scalar_one()
        assert row.last_status == "failed"
        assert row.last_error and "network" in row.last_error
        await s.execute(delete(Integration).where(Integration.name == "github"))
        await s.commit()
