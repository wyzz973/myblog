"""Media filesystem adapter: validation, save, delete, url_for."""
from __future__ import annotations


class MediaError(Exception):
    """Raised when an upload fails validation."""


ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB


async def save(content: bytes, *, declared_mime: str, original_name: str):
    if len(content) > MAX_BYTES:
        raise MediaError("too large, max 10MB")
    if declared_mime not in ALLOWED_MIME:
        raise MediaError(f"unsupported mime: {declared_mime}")
    raise NotImplementedError("further validation not yet implemented")
