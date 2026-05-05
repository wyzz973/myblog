"""GitHub GraphQL client: contribution counts + owned public repos."""
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


# Process-local repo-listing cache. The GitHub API has rate limits; if
# the owner reopens the import modal repeatedly we don't want to hit
# them. 10-minute TTL is short enough that newly-created repos appear
# without a server restart, long enough that admin churn is invisible.
_REPOS_CACHE: dict[str, tuple[float, list[dict]]] = {}
_REPOS_CACHE_TTL = 600  # seconds


def _repos_cache_clear() -> None:
    """Test hook — production code should never call this."""
    _REPOS_CACHE.clear()


async def fetch_repos(token: str, login: str, *, limit: int = 100) -> list[dict]:
    """Return the owner's public repos as
    [{name, description, primaryLanguage, stargazerCount, isArchived, url}].

    Cached per (login) for ~10 minutes. The cache key intentionally
    excludes the token: a single owner has one effective token at a
    time, and rotating it doesn't change the repo list.
    """
    import time
    now = time.time()
    cached = _REPOS_CACHE.get(login)
    if cached is not None and now - cached[0] < _REPOS_CACHE_TTL:
        return cached[1]

    query = """
    query($login: String!, $first: Int!) {
      user(login: $login) {
        repositories(
          first: $first,
          privacy: PUBLIC,
          ownerAffiliations: OWNER,
          orderBy: { field: PUSHED_AT, direction: DESC }
        ) {
          nodes {
            name
            description
            isArchived
            isFork
            stargazerCount
            url
            primaryLanguage { name }
          }
        }
      }
    }
    """
    headers = {"Authorization": f"bearer {token}"}
    variables = {"login": login, "first": min(limit, 100)}
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(
                API,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=HTTP_TIMEOUT,
            )
        if r.status_code != 200:
            log.warning("github.repos_http_error", status=r.status_code, body=r.text[:256])
            return []
        data = r.json()
        if data.get("errors"):
            log.warning("github.repos_graphql_error", errors=data["errors"])
            return []
        nodes = data["data"]["user"]["repositories"]["nodes"] or []
        repos = [
            {
                "name": n["name"],
                "description": n.get("description") or "",
                "lang": (n.get("primaryLanguage") or {}).get("name") or "",
                "stars": int(n.get("stargazerCount") or 0),
                "archived": bool(n.get("isArchived")),
                "fork": bool(n.get("isFork")),
                "url": n.get("url") or "",
            }
            for n in nodes
        ]
        _REPOS_CACHE[login] = (now, repos)
        return repos
    except httpx.TimeoutException as e:
        log.warning("github.repos_timeout", error=str(e))
    except httpx.HTTPError as e:
        log.warning("github.repos_http_exception", error=str(e))
    except Exception as e:  # noqa: BLE001
        log.warning("github.repos_unexpected", error=repr(e))
    return []


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


# fetch_repos is defined near the top of the file alongside the cache.
# (Earlier revisions had a second definition here that didn't cache and
# returned a slightly different shape with `fork`. Task 24a unifies on
# the cached, URL-bearing top-of-file version.)
