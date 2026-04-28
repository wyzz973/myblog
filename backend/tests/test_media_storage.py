"""media_storage validation + IO unit tests."""
from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.services.media_storage import (
    ALLOWED_MIME,
    MAX_BYTES,
    MediaError,
    save,
)


@pytest.fixture
def media_dir(tmp_path, monkeypatch):
    """Override media_storage._media_dir to point at tmp_path for the test."""
    from app.services import media_storage
    monkeypatch.setattr(media_storage, "_media_dir", lambda: tmp_path)
    return tmp_path


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


def _png_bytes(w: int = 4, h: int = 3) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 128, 0)).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int = 5, h: int = 7) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(0, 0, 200)).save(buf, format="JPEG")
    return buf.getvalue()


async def test_save_accepts_png_with_dims(media_dir):
    from app.services import media_storage
    res = await media_storage.save(
        _png_bytes(w=10, h=20), declared_mime="image/png", original_name="cat.png"
    )
    assert res.mime_type == "image/png"
    assert res.width == 10
    assert res.height == 20
    assert res.size == len(_png_bytes(w=10, h=20))


async def test_save_canonicalizes_mime_when_extension_lies(media_dir):
    """Declared image/png but bytes are JPEG → canonicalized to image/jpeg."""
    from app.services import media_storage
    jpeg = _jpeg_bytes(w=5, h=7)
    res = await media_storage.save(
        jpeg, declared_mime="image/png", original_name="liar.png"
    )
    assert res.mime_type == "image/jpeg"


async def test_save_rejects_decode_failure(media_dir):
    from app.services import media_storage
    with pytest.raises(MediaError, match="not a valid image"):
        await media_storage.save(
            b"definitely not an image",
            declared_mime="image/png",
            original_name="garbage.png",
        )


SVG_OK = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><circle cx="5" cy="5" r="4"/></svg>'
SVG_SCRIPT = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
SVG_ONLOAD = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect/></svg>'


async def test_save_accepts_clean_svg(media_dir):
    from app.services import media_storage
    res = await media_storage.save(
        SVG_OK, declared_mime="image/svg+xml", original_name="icon.svg"
    )
    assert res.mime_type == "image/svg+xml"
    assert res.width is None
    assert res.height is None


async def test_save_rejects_svg_with_script(media_dir):
    from app.services import media_storage
    with pytest.raises(MediaError, match="svg with script"):
        await media_storage.save(
            SVG_SCRIPT, declared_mime="image/svg+xml", original_name="bad.svg"
        )


async def test_save_rejects_svg_with_onload(media_dir):
    from app.services import media_storage
    with pytest.raises(MediaError, match="svg with script"):
        await media_storage.save(
            SVG_ONLOAD, declared_mime="image/svg+xml", original_name="bad.svg"
        )


async def test_delete_removes_file(media_dir):
    from app.services import media_storage
    res = await media_storage.save(
        _png_bytes(), declared_mime="image/png", original_name="x.png"
    )
    full = media_dir / res.storage_path
    assert full.exists()
    await media_storage.delete(res.storage_path)
    assert not full.exists()


async def test_delete_is_idempotent(media_dir):
    from app.services import media_storage
    # Should not raise even though the file was never created.
    await media_storage.delete("aa/never-existed.png")


def test_url_for_returns_media_prefix():
    from app.services.media_storage import url_for
    assert url_for("7f/7f3e-cat.png") == "/media/7f/7f3e-cat.png"


# --- Billion-laughs / XXE regression (B1) ---

BILLION_LAUGHS_SVG = (
    b'<?xml version="1.0"?>'
    b'<!DOCTYPE lolz [<!ENTITY lol "lol">'
    b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;">'
    b']>'
    b'<svg xmlns="http://www.w3.org/2000/svg">&lol2;</svg>'
)


async def test_save_rejects_billion_laughs_svg(media_dir):
    from app.services.media_storage import save
    with pytest.raises(MediaError, match="invalid svg xml"):
        await save(
            BILLION_LAUGHS_SVG,
            declared_mime="image/svg+xml",
            original_name="bomb.svg",
        )


# --- ASCII filename sanitization regression (B2) ---


async def test_save_strips_non_ascii_from_filename(media_dir):
    from app.services.media_storage import save
    res = await save(
        _png_bytes(), declared_mime="image/png", original_name="猫咪.png"
    )
    # The Chinese characters are stripped; only ".png" survives the filter.
    assert res.storage_path.endswith(".png")
    assert all(c.isascii() for c in res.storage_path)


async def test_save_strips_rtl_override_from_filename(media_dir):
    from app.services.media_storage import save
    # Right-to-left override would let "evil‮gpj.exe" display as "evilexe.jpg".
    res = await save(
        _png_bytes(), declared_mime="image/png",
        original_name="evil‮gpj.png",
    )
    assert "‮" not in res.storage_path
    assert all(c.isascii() for c in res.storage_path)


async def test_save_falls_back_to_file_when_name_is_empty_after_sanitize(media_dir):
    from app.services.media_storage import save
    res = await save(
        _png_bytes(), declared_mime="image/png", original_name="🐱"
    )
    # All chars stripped; helper falls back to "file".
    assert res.storage_path.endswith("-file")


# --- Pillow decompression bomb guard (I1) ---


async def test_save_rejects_decompression_bomb(media_dir, monkeypatch):
    """A small image with a tightened MAX_IMAGE_PIXELS triggers the bomb guard."""
    from app.services import media_storage
    # Lower the pixel cap so even a 200x200 image is "too large".
    monkeypatch.setattr(media_storage.Image, "MAX_IMAGE_PIXELS", 100)
    with pytest.raises(MediaError, match="not a valid image"):
        await media_storage.save(
            _png_bytes(w=200, h=200),
            declared_mime="image/png",
            original_name="bomb.png",
        )


# --- SVG namespaced <script> element (test gap 5) ---


SVG_NAMESPACED_SCRIPT = (
    b'<svg xmlns="http://www.w3.org/2000/svg" '
    b'xmlns:xhtml="http://www.w3.org/1999/xhtml">'
    b'<xhtml:script>alert(1)</xhtml:script>'
    b'</svg>'
)


async def test_save_rejects_namespaced_script(media_dir):
    from app.services.media_storage import save
    with pytest.raises(MediaError, match="svg with script"):
        await save(
            SVG_NAMESPACED_SCRIPT, declared_mime="image/svg+xml",
            original_name="ns.svg",
        )


# --- 0-byte file (test gap 7) ---


async def test_save_rejects_zero_byte_file(media_dir):
    from app.services.media_storage import save
    with pytest.raises(MediaError, match="not a valid image"):
        await save(b"", declared_mime="image/png", original_name="empty.png")


# --- Documented limit: <foreignObject> is NOT rejected (test gap 6) ---


SVG_FOREIGNOBJECT = (
    b'<svg xmlns="http://www.w3.org/2000/svg">'
    b'<foreignObject><body><p>hi</p></body></foreignObject>'
    b'</svg>'
)


async def test_save_accepts_svg_with_foreign_object(media_dir):
    """Documents the intentional limit of _validate_svg: it only filters
    <script> and on*-attrs. <foreignObject> with non-script HTML is
    accepted because the public site renders SVG via <img src>, not
    <object>/<iframe>; an attacker cannot execute the embedded HTML
    via an <img> tag. If the rendering surface ever changes, tighten
    _validate_svg accordingly."""
    from app.services.media_storage import save
    res = await save(
        SVG_FOREIGNOBJECT, declared_mime="image/svg+xml",
        original_name="fo.svg",
    )
    assert res.mime_type == "image/svg+xml"
