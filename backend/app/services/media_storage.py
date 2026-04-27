"""Media filesystem adapter: validation, save, delete, url_for."""
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import get_settings


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

# Tests override this to point at a tmpdir.
MEDIA_DIR: Path = get_settings().data_dir / "media"


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


async def save(
    content: bytes, *, declared_mime: str, original_name: str
) -> SaveResult:
    if len(content) > MAX_BYTES:
        raise MediaError("too large, max 10MB")
    if declared_mime not in ALLOWED_MIME:
        raise MediaError(f"unsupported mime: {declared_mime}")

    if declared_mime == "image/svg+xml":
        _validate_svg(content)
        storage_path = _build_storage_path(original_name, "image/svg+xml")
        full = MEDIA_DIR / storage_path
        full.parent.mkdir(parents=True, exist_ok=True)
        tmp = full.with_suffix(full.suffix + ".tmp")
        tmp.write_bytes(content)
        tmp.rename(full)
        return SaveResult(
            storage_path=storage_path,
            mime_type="image/svg+xml",
            size=len(content),
            width=None,
            height=None,
        )

    try:
        img = Image.open(BytesIO(content))
        img.load()  # force decode so corrupt files raise here
    except (UnidentifiedImageError, OSError) as e:
        raise MediaError(f"not a valid image: {e}") from e

    canonical = _PIL_FORMAT_TO_MIME.get(img.format)
    if canonical is None:
        raise MediaError(f"unsupported pil format: {img.format}")

    storage_path = _build_storage_path(original_name, canonical)
    full = MEDIA_DIR / storage_path
    full.parent.mkdir(parents=True, exist_ok=True)
    tmp = full.with_suffix(full.suffix + ".tmp")
    tmp.write_bytes(content)
    tmp.rename(full)

    return SaveResult(
        storage_path=storage_path,
        mime_type=canonical,
        size=len(content),
        width=img.width,
        height=img.height,
    )


async def delete(storage_path: str) -> None:
    """Remove the stored file. No-op if already missing."""
    full = MEDIA_DIR / storage_path
    try:
        full.unlink()
    except FileNotFoundError:
        return


def _build_storage_path(original_name: str, mime_type: str) -> str:
    """Bucket prefix from UUID → "7f/7f3e1abc-orig.png"."""
    safe_name = "".join(
        c for c in original_name if c.isalnum() or c in ("-", "_", ".")
    ) or "file"
    new_uuid = uuid.uuid4().hex
    bucket = new_uuid[:2]
    return f"{bucket}/{new_uuid}-{safe_name}"


def _validate_svg(content: bytes) -> None:
    """Reject SVGs containing <script> elements or `on*` event-handler attributes."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise MediaError(f"invalid svg xml: {e}") from e
    for el in root.iter():
        # local tag name strips XML namespace, e.g. "{ns}script" → "script".
        local = el.tag.rsplit("}", 1)[-1].lower()
        if local == "script":
            raise MediaError("svg with script content not allowed")
        for attr in el.attrib:
            local_attr = attr.rsplit("}", 1)[-1].lower()
            if local_attr.startswith("on"):
                raise MediaError("svg with script content not allowed")
