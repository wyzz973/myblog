"""Media filesystem adapter: validation, save, delete, url_for."""
from __future__ import annotations

import re
import uuid
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from xml.etree.ElementTree import ParseError as XMLParseError

from defusedxml import ElementTree as DefusedET
from PIL import Image, UnidentifiedImageError

from app.config import get_settings

# Limit pixel count to defeat decompression bombs.
# 40MP > any realistic blog image; well below the default 89MP.
Image.MAX_IMAGE_PIXELS = 40_000_000

_EVENT_ATTR_RE = re.compile(r"on[a-z]+$")


class MediaError(Exception):
    """Raised when an upload fails validation."""


ALLOWED_MIME = {
    "image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml",
}
MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Pillow's `format` strings → canonical mime types.
_PIL_FORMAT_TO_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


def _media_dir() -> Path:
    return get_settings().data_dir / "media"


@dataclass
class SaveResult:
    storage_path: str
    mime_type: str
    size: int
    width: int | None
    height: int | None


def url_for(storage_path: str) -> str:
    """Return the public URL for a stored asset. S3 swap changes only this."""
    return f"/media/{storage_path}"


def _is_event_attr(attr: str) -> bool:
    return bool(_EVENT_ATTR_RE.match(attr))


async def save(
    content: bytes, *, declared_mime: str, original_name: str
) -> SaveResult:
    if len(content) > MAX_BYTES:
        raise MediaError(f"too large, max {MAX_BYTES // (1024 * 1024)}MB")
    if declared_mime not in ALLOWED_MIME:
        raise MediaError(f"unsupported mime: {declared_mime}")

    if declared_mime == "image/svg+xml":
        _validate_svg(content)
        storage_path = _build_storage_path(original_name, "image/svg+xml")
        full = _media_dir() / storage_path
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp = full.with_suffix(full.suffix + ".tmp")
        tmp.write_bytes(content)
        try:
            tmp.rename(full)
        except OSError:
            tmp.unlink(missing_ok=True)
            raise
        return SaveResult(
            storage_path=storage_path,
            mime_type="image/svg+xml",
            size=len(content),
            width=None,
            height=None,
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(BytesIO(content))
            img.load()  # force decode so corrupt files raise here
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise MediaError(f"not a valid image: {e}") from e

    canonical = _PIL_FORMAT_TO_MIME.get(img.format)
    if canonical is None:
        raise MediaError(f"unsupported pil format: {img.format}")

    storage_path = _build_storage_path(original_name, canonical)
    full = _media_dir() / storage_path
    full.parent.mkdir(parents=True, exist_ok=True)
    tmp = full.with_suffix(full.suffix + ".tmp")
    tmp.write_bytes(content)
    try:
        tmp.rename(full)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise

    return SaveResult(
        storage_path=storage_path,
        mime_type=canonical,
        size=len(content),
        width=img.width,
        height=img.height,
    )


async def delete(storage_path: str) -> None:
    """Remove the stored file. No-op if already missing."""
    full = _media_dir() / storage_path
    try:
        full.unlink()
    except FileNotFoundError:
        return


def _build_storage_path(original_name: str, mime_type: str) -> str:
    """Bucket prefix from UUID → "7f/7f3e1abc-orig.png"."""
    safe_name = "".join(
        c for c in original_name
        if c.isascii() and (c.isalnum() or c in ("-", "_", "."))
    ) or "file"
    new_uuid = uuid.uuid4().hex
    return f"{new_uuid[:2]}/{new_uuid}-{safe_name}"


def _validate_svg(content: bytes) -> None:
    """Reject SVGs containing <script> elements or `on*` event-handler attributes."""
    try:
        root = DefusedET.fromstring(
            content,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (XMLParseError, ValueError) as e:
        raise MediaError(f"invalid svg xml: {e}") from e
    for el in root.iter():
        # local tag name strips XML namespace, e.g. "{ns}script" → "script".
        local = el.tag.rsplit("}", 1)[-1].lower()
        if local == "script":
            raise MediaError("svg with script content not allowed")
        for attr in el.attrib:
            local_attr = attr.rsplit("}", 1)[-1].lower()
            if _is_event_attr(local_attr):
                raise MediaError("svg with script content not allowed")
