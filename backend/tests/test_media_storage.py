"""media_storage validation + IO unit tests."""
from __future__ import annotations

import pytest

from app.services.media_storage import (
    ALLOWED_MIME,
    MAX_BYTES,
    MediaError,
    save,
)


async def test_save_rejects_too_large():
    big = b"x" * (MAX_BYTES + 1)
    with pytest.raises(MediaError, match="too large"):
        await save(big, declared_mime="image/png", original_name="big.png")


async def test_save_rejects_unsupported_mime():
    with pytest.raises(MediaError, match="unsupported mime"):
        await save(b"%PDF-1.4...", declared_mime="application/pdf", original_name="doc.pdf")


def test_allowed_mime_set_is_exhaustive():
    """Tighten this test if the spec ever changes the whitelist."""
    assert ALLOWED_MIME == {
        "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
    }
