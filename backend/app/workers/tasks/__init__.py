"""ARQ task implementations, organized by domain."""
from __future__ import annotations

from app.workers.tasks.analytics import analytics_rollup
from app.workers.tasks.auth import cleanup_expired_magic_links
from app.workers.tasks.email import send_email_task
from app.workers.tasks.github import sync_github_contrib
from app.workers.tasks.housekeeping import prune_event_log
from app.workers.tasks.posts import publish_scheduled_posts, recompute_post_word_counts

__all__ = [
    "analytics_rollup",
    "cleanup_expired_magic_links",
    "prune_event_log",
    "publish_scheduled_posts",
    "recompute_post_word_counts",
    "send_email_task",
    "sync_github_contrib",
]
