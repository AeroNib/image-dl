from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImageTarget:
    """Represents a single image to download."""

    url: str | None
    source_tag: str
    original_ref: str
    inline_content: bytes | None = None


@dataclass
class DownloadResult:
    """Result of a single download attempt."""

    target: ImageTarget
    filepath: Path | None = None
    status: str = "ok"  # "ok", "skipped", "error"
    error: str | None = None
    size_bytes: int = 0
