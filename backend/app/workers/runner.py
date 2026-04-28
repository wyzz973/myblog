"""ARQ worker entry point. Registers tasks for both ARQ runtime and inline mode."""
from __future__ import annotations

from datetime import UTC

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import get_settings
from app.workers import queue as q
from app.workers import tasks as t

# Register every task so enqueue() inline-mode can find them by name
q.register("send_email_task", t.send_email_task)
q.register("publish_scheduled_posts", t.publish_scheduled_posts)
q.register("cleanup_expired_magic_links", t.cleanup_expired_magic_links)
q.register("prune_event_log", t.prune_event_log)
q.register("recompute_post_word_counts", t.recompute_post_word_counts)
q.register("sync_github_contrib", t.sync_github_contrib)
q.register("analytics_rollup", t.analytics_rollup)
q.register("build_export_task", t.build_export_task)
q.register("check_pending_site_deletion", t.check_pending_site_deletion)
q.register("prune_old_exports", t.prune_old_exports)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Pin cron to UTC so retention/sync windows match comments regardless of host TZ.
    timezone = UTC
    functions = [
        t.send_email_task,
        t.publish_scheduled_posts,
        t.cleanup_expired_magic_links,
        t.prune_event_log,
        t.recompute_post_word_counts,
        t.sync_github_contrib,
        t.analytics_rollup,
        t.build_export_task,
        t.check_pending_site_deletion,
        t.prune_old_exports,
    ]
    cron_jobs: list = [
        cron(t.publish_scheduled_posts, minute=set(range(0, 60))),  # every minute
        cron(t.cleanup_expired_magic_links, minute={10, 40}),
        cron(t.prune_event_log, hour={3}, minute={0}),  # 03:00 UTC daily
        cron(t.sync_github_contrib, minute={5}),  # :05 every hour (UTC)
        cron(t.analytics_rollup, hour={3}, minute={0}),  # 03:00 UTC daily
        cron(t.check_pending_site_deletion, minute={0}),         # hourly :00
        cron(t.prune_old_exports, hour={3}, minute={30}),        # daily 03:30 UTC
    ]
    max_jobs = 4
