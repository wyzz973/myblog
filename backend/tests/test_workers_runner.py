"""Pin cron registrations against accidental deletion or schedule drift."""
from __future__ import annotations

from datetime import UTC

from app.workers.runner import WorkerSettings


def test_worker_timezone_is_utc():
    assert WorkerSettings.timezone is UTC


def test_cron_jobs_registered_with_expected_schedules():
    """All four spec-mandated cron entries must be registered with the right tick."""
    by_name: dict[str, object] = {}
    for cj in WorkerSettings.cron_jobs:
        # arq's CronJob exposes the underlying coroutine as `coroutine`.
        coro = getattr(cj, "coroutine", None) or getattr(cj, "_coroutine", None)
        name = coro.__name__ if coro is not None else getattr(cj, "name", repr(cj))
        by_name[name] = cj

    assert "publish_scheduled_posts" in by_name
    assert "cleanup_expired_magic_links" in by_name
    assert "prune_event_log" in by_name
    assert "sync_github_contrib" in by_name

    # cleanup runs at :10 and :40
    minute = getattr(by_name["cleanup_expired_magic_links"], "minute", None)
    assert minute == {10, 40}, f"got {minute!r}"

    # prune runs at 03:00 hour
    hour = getattr(by_name["prune_event_log"], "hour", None)
    minute = getattr(by_name["prune_event_log"], "minute", None)
    assert hour == {3} and minute == {0}, f"got hour={hour!r} minute={minute!r}"

    # github sync at :05 every hour
    minute = getattr(by_name["sync_github_contrib"], "minute", None)
    assert minute == {5}, f"got {minute!r}"


def test_all_six_tasks_listed_in_functions():
    names = {f.__name__ for f in WorkerSettings.functions}
    assert names == {
        "send_email_task",
        "publish_scheduled_posts",
        "cleanup_expired_magic_links",
        "prune_event_log",
        "recompute_post_word_counts",
        "sync_github_contrib",
    }
