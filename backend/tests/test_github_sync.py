"""Mock GraphQL responses; service must hit the right query and parse correctly."""
from datetime import date
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.services.github import fetch_contributions, ping


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
