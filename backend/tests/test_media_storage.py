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


from io import BytesIO
from PIL import Image


def _png_bytes(w: int = 4, h: int = 3) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 128, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int = 5, h: int = 7) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 0, 200)).save(buf, format="JPEG")
    return buf.getvalue()


async def test_save_accepts_png_with_dims(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    res = await media_storage.save(
        _png_bytes(w=10, h=20), declared_mime="image/png", original_name="cat.png"
    )
    assert res.mime_type == "image/png"
    assert res.width == 10
    assert res.height == 20
    assert res.size == len(_png_bytes(w=10, h=20))


async def test_save_canonicalizes_mime_when_extension_lies(tmp_path, monkeypatch):
    """Declared image/png but bytes are JPEG → canonicalized to image/jpeg."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    jpeg = _jpeg_bytes(w=5, h=7)
    res = await media_storage.save(
        jpeg, declared_mime="image/png", original_name="liar.png"
    )
    assert res.mime_type == "image/jpeg"


async def test_save_rejects_decode_failure(tmp_path, monkeypatch):
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "MEDIA_DIR", tmp_path)
    with pytest.raises(MediaError, match="not a valid image"):
        await media_storage.save(
            b"definitely not an image",
            declared_mime="image/png",
            original_name="garbage.png",
        )
