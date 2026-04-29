from __future__ import annotations

import hashlib
import re


def serialize_svg_html(outer_html: str) -> bytes:
    """Convert an SVG element's outer HTML into a standalone SVG file.

    Adds the xmlns attribute if missing so the output is a valid standalone SVG.
    The outer_html comes from Playwright's element.evaluate("el => el.outerHTML").
    """
    if 'xmlns="' not in outer_html and "xmlns='" not in outer_html:
        outer_html = outer_html.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
    return (declaration + outer_html).encode("utf-8")


def generate_svg_filename(svg_bytes: bytes, index: int) -> str:
    """Generate a filename for an inline SVG.

    Uses the <title> element text if present, otherwise falls back to
    ``inline-svg-{index}``.
    """
    text = svg_bytes.decode("utf-8", errors="replace")
    match = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()[:80]
        name = "".join(c if c.isalnum() or c in "-_ " else "" for c in title)
        name = name.strip().replace(" ", "-")
        if name:
            return f"{name}.svg"
    return f"inline-svg-{index}.svg"


def svg_content_hash(svg_bytes: bytes) -> str:
    """Return a short SHA-256 hex digest for deduplication."""
    return hashlib.sha256(svg_bytes).hexdigest()[:12]
