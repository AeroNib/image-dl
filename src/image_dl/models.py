from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class CapturedImage:
    """An image captured via network interception or DOM extraction."""

    url: str | None
    data: bytes
    content_type: str | None
    source: str  # "network" or "inline-svg"


@dataclass
class SaveResult:
    """Result of saving a single image to disk."""

    image: CapturedImage
    filepath: Path | None = None
    status: str = "ok"  # "ok", "error"
    error: str | None = None
    size_bytes: int = 0
