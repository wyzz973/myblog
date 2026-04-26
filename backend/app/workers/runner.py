"""ARQ worker entry point. Registers tasks for both ARQ runtime and inline mode."""
from __future__ import annotations

from arq.connections import RedisSettings
from arq.cron import cron

from app.config import get_settings
from app.workers import queue as q
from app.workers import tasks as t


# Register every task so enqueue() inline-mode can find them by name
q.register("send_email_task", t.send_email_task)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [t.send_email_task]
    cron_jobs: list = []
    max_jobs = 4
