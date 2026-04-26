"""ARQ worker entry point. Registers tasks for both ARQ runtime and inline mode."""
from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import get_settings
from app.workers import queue as q
from app.workers import tasks as t


# Register every task so enqueue() inline-mode can find them by name
q.register("send_email_task", t.send_email_task)
q.register("publish_scheduled_posts", t.publish_scheduled_posts)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [t.send_email_task, t.publish_scheduled_posts]
    cron_jobs: list = [
        cron(t.publish_scheduled_posts, minute=set(range(0, 60))),  # every minute
    ]
    max_jobs = 4
