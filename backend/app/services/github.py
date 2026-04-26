"""GitHub GraphQL client (only contribution counts; YAGNI for the rest)."""
from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

import httpx

API = "https://api.github.com/graphql"
HTTP_TIMEOUT = 10.0


def _level(count: int) -> int:
    """GitHub's official 0..4 contribution levels by daily count."""
    if count == 0:
        return 0
    if count <= 3:
        return 1
    if count <= 9:
        return 2
    if count <= 19:
        return 3
    return 4


async def ping(token: str) -> str | None:
    """Returns the viewer login on success, None on failure."""
    query = "{ viewer { login } }"
    headers = {"Authorization": f"bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(API, json={"query": query}, headers=headers, timeout=HTTP_TIMEOUT)
        if r.status_code != 200:
            return None
        data = r.json()
        if data.get("errors"):
            return None
        return data["data"]["viewer"]["login"]
    except Exception:  # noqa: BLE001
        return None


async def fetch_contributions(token: str, login: str) -> list[dict]:
    """Returns [{day: date, count: int, level: int}] for the trailing 52 weeks."""
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar {
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    headers = {"Authorization": f"bearer {token}"}
    async with httpx.AsyncClient() as client:
        r = await client.post(
            API,
            json={"query": query, "variables": {"login": login}},
            headers=headers,
            timeout=HTTP_TIMEOUT,
        )
    if r.status_code != 200:
        return []
    data = r.json().get("data", {})
    user = data.get("user")
    if user is None:
        return []
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    out: list[dict] = []
    for w in weeks:
        for d in w["contributionDays"]:
            day = datetime.strptime(d["date"], "%Y-%m-%d").date()
            count = int(d["contributionCount"])
            out.append({"day": day, "count": count, "level": _level(count)})
    return out
