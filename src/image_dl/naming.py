from __future__ import annotations

import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
    "image/tiff": ".tiff",
    "image/avif": ".avif",
}

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_MAX_FILENAME_LEN = 200


def filename_from_url(url: str) -> str:
    """Extract a filename from a URL path, stripping query params."""
    parsed = urlparse(url)
    path = PurePosixPath(parsed.path)
    name = path.name
    if not name or name == "/":
        return "image"
    return name


def sanitize_filename(name: str) -> str:
    """Remove invalid filesystem characters, collapse whitespace, and truncate."""
    name = _INVALID_CHARS.sub("", name)
    name = re.sub(r"\s+", "-", name.strip())
    if not name:
        return "image"
    stem, _, ext = name.rpartition(".")
    if stem and ext:
        stem = stem[:_MAX_FILENAME_LEN]
        return f"{stem}.{ext}"
    return name[:_MAX_FILENAME_LEN]


def deduplicate_filename(name: str, existing: set[str]) -> str:
    """Append -1, -2, etc. before the extension until the name is unique."""
    if name not in existing:
        return name
    stem, dot, ext = name.rpartition(".")
    if not stem:
        stem, dot, ext = name, "", ""
    counter = 1
    while True:
        candidate = f"{stem}-{counter}{dot}{ext}"
        if candidate not in existing:
            return candidate
        counter += 1


def guess_extension_from_content_type(content_type: str | None) -> str | None:
    """Map a Content-Type header value to a file extension."""
    if not content_type:
        return None
    mime = content_type.split(";", 1)[0].strip().lower()
    return MIME_TO_EXT.get(mime)


_KNOWN_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif",
    ".bmp", ".ico", ".tiff", ".tif", ".avif",
}


def _has_image_extension(name: str) -> bool:
    """Check if a filename already has a recognized image extension."""
    _, dot, ext = name.rpartition(".")
    return bool(dot) and f".{ext.lower()}" in _KNOWN_EXTENSIONS


def resolve_filename(
    url: str | None,
    content_type: str | None,
    inline_index: int | None,
    existing: set[str],
) -> str:
    """Full filename resolution pipeline: extract, sanitize, fix extension, deduplicate."""
    if url is None:
        # Inline SVG — caller provides index
        name = f"inline-svg-{inline_index}.svg"
    else:
        name = sanitize_filename(filename_from_url(url))
        if not _has_image_extension(name):
            guessed = guess_extension_from_content_type(content_type)
            if guessed:
                name = f"{name}{guessed}"
    name = deduplicate_filename(name, existing)
    existing.add(name)
    return name
