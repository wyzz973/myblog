"""Resolve the originating client IP, optionally from X-Forwarded-For
when the immediate peer is a trusted proxy.

For rate-limit keys / event_log entries we want a stable hash of this IP.
"""
from __future__ import annotations

from fastapi import Request

from app.config import get_settings
from app.services.hashing import ip_hash


def client_ip_from(request: Request) -> str:
    """Returns the best-known client IP as a string."""
    peer = request.client.host if request.client else "unknown"
    settings = get_settings()
    if peer in settings.trusted_proxies:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            # left-most is the originating client per RFC 7239 / X-F-F convention
            return xff.split(",")[0].strip()
    return peer


def client_ip_key_part(request: Request) -> str:
    """Hashed IP fragment safe to embed in Redis keys / event_log meta."""
    return ip_hash(client_ip_from(request))[:16]
