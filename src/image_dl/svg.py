from __future__ import annotations

import hashlib

from bs4 import Tag


def serialize_svg_element(svg_tag: Tag) -> bytes:
    """Serialize a BeautifulSoup <svg> Tag into a standalone SVG file.

    Adds the xmlns attribute if missing so the output is a valid standalone SVG.
    """
    if not svg_tag.get("xmlns"):
        svg_tag["xmlns"] = "http://www.w3.org/2000/svg"
    svg_str = str(svg_tag)
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    return (declaration + svg_str).encode("utf-8")


def generate_svg_filename(svg_bytes: bytes, index: int) -> str:
    """Generate a filename for an inline SVG.

    Uses the <title> element text if present, otherwise falls back to
    ``inline-svg-{index}``.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(svg_bytes, "lxml-xml")
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        # Sanitize title for use as filename
        name = title_tag.string.strip()[:80]
        name = "".join(c if c.isalnum() or c in "-_ " else "" for c in name)
        name = name.strip().replace(" ", "-") or f"inline-svg-{index}"
    else:
        name = f"inline-svg-{index}"
    return f"{name}.svg"


def svg_content_hash(svg_bytes: bytes) -> str:
    """Return a short SHA-256 hex digest for deduplication."""
    return hashlib.sha256(svg_bytes).hexdigest()[:12]
