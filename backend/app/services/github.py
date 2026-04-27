"""GitHub GraphQL client (only contribution counts; YAGNI for the rest)."""
from __future__ import annotations

from datetime import datetime

import httpx
import structlog

log = structlog.get_logger(__name__)

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
            log.warning("github.ping_http_error", status=r.status_code, body=r.text[:256])
            return None
        data = r.json()
        if data.get("errors"):
            log.warning("github.ping_graphql_error", errors=data["errors"])
            return None
        return data["data"]["viewer"]["login"]
    except httpx.TimeoutException as e:
        log.warning("github.ping_timeout", error=str(e))
    except httpx.HTTPError as e:
        log.warning("github.ping_http_exception", error=str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("github.ping_unexpected", error=repr(e))
    return None


async def fetch_contributions(token: str, login: str, weeks: int = 52) -> list[dict]:
    """Returns [{day: date, count: int, level: int}] for the trailing `weeks` weeks.

    GitHub's contributionCalendar always returns ~53 weeks; we trim to the
    requested window by keeping the trailing `weeks * 7` days.
    """
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
        log.warning("github.fetch_http_error", status=r.status_code, body=r.text[:256], login=login)
        return []
    payload = r.json()
    if payload.get("errors"):
        log.warning("github.fetch_graphql_error", errors=payload["errors"], login=login)
        return []
    data = payload.get("data", {})
    user = data.get("user")
    if user is None:
        log.warning("github.fetch_no_user", login=login)
        return []
    cal_weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    out: list[dict] = []
    for w in cal_weeks:
        for d in w["contributionDays"]:
            day = datetime.strptime(d["date"], "%Y-%m-%d").date()
            count = int(d["contributionCount"])
            out.append({"day": day, "count": count, "level": _level(count)})
    if weeks > 0 and len(out) > weeks * 7:
        out = out[-weeks * 7 :]
    return out
