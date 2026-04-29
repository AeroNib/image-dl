from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from image_dl.models import ImageTarget
from image_dl.svg import serialize_svg_element, svg_content_hash

SUPPORTED_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".webp", ".svg", ".gif",
    ".bmp", ".ico", ".tiff", ".tif", ".avif",
}

IMAGE_CONTENT_TYPES: set[str] = {
    "image/jpeg", "image/png", "image/webp", "image/svg+xml",
    "image/gif", "image/bmp", "image/x-icon", "image/vnd.microsoft.icon",
    "image/tiff", "image/avif",
}

_DEFAULT_USER_AGENT = "image-dl/0.1 (https://github.com/image-dl)"
_CSS_URL_RE = re.compile(r"url\(['\"]?(.*?)['\"]?\)", re.IGNORECASE)


class ScraperError(Exception):
    pass


def fetch_page(
    url: str,
    timeout: int = 30,
    user_agent: str | None = None,
) -> tuple[str, str]:
    """Fetch the HTML content of a page.

    Returns (html_content, final_url) where final_url accounts for redirects.
    """
    headers = {"User-Agent": user_agent or _DEFAULT_USER_AGENT}
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ScraperError(
            f"HTTP {exc.response.status_code} fetching {url}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ScraperError(f"Failed to fetch {url}: {exc}") from exc
    return response.text, str(response.url)


def extract_images(
    html: str,
    page_url: str,
    include_inline_svg: bool = True,
) -> list[ImageTarget]:
    """Extract all image targets from HTML content.

    Runs all sub-extractors and deduplicates the results.
    """
    soup = BeautifulSoup(html, "lxml")
    targets: list[ImageTarget] = []

    targets.extend(_extract_img_src(soup, page_url))
    targets.extend(_extract_img_srcset(soup, page_url))
    targets.extend(_extract_picture_sources(soup, page_url))
    targets.extend(_extract_css_background_images(soup, page_url))
    targets.extend(_extract_link_icons(soup, page_url))
    targets.extend(_extract_meta_og_images(soup, page_url))
    if include_inline_svg:
        targets.extend(_extract_inline_svgs(soup))

    return _deduplicate(targets)


def _extract_img_src(soup: BeautifulSoup, base_url: str) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    for img in soup.find_all("img", src=True):
        url = _resolve_url(img["src"], base_url)
        if url:
            results.append(ImageTarget(
                url=url, source_tag="img", original_ref=img["src"],
            ))
    return results


def _extract_img_srcset(soup: BeautifulSoup, base_url: str) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    for tag in soup.find_all(["img", "source"], srcset=True):
        for entry in _parse_srcset(tag["srcset"]):
            url = _resolve_url(entry, base_url)
            if url:
                results.append(ImageTarget(
                    url=url, source_tag="srcset", original_ref=entry,
                ))
    return results


def _extract_picture_sources(soup: BeautifulSoup, base_url: str) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    for source in soup.select("picture source[src]"):
        url = _resolve_url(source["src"], base_url)
        if url:
            results.append(ImageTarget(
                url=url, source_tag="picture", original_ref=source["src"],
            ))
    return results


def _extract_css_background_images(
    soup: BeautifulSoup, base_url: str,
) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    for tag in soup.find_all(style=True):
        style = tag["style"]
        for match in _CSS_URL_RE.finditer(style):
            ref = match.group(1).strip()
            if not ref or ref.startswith("data:"):
                continue
            url = _resolve_url(ref, base_url)
            if url and _is_image_url(url):
                results.append(ImageTarget(
                    url=url, source_tag="css-bg", original_ref=ref,
                ))
    return results


def _extract_link_icons(soup: BeautifulSoup, base_url: str) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    for link in soup.find_all("link", href=True):
        rel = " ".join(link.get("rel", []))
        if re.search(r"icon", rel, re.IGNORECASE):
            url = _resolve_url(link["href"], base_url)
            if url:
                results.append(ImageTarget(
                    url=url, source_tag="link-icon", original_ref=link["href"],
                ))
    return results


def _extract_meta_og_images(soup: BeautifulSoup, base_url: str) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    selectors = [
        ("meta", {"property": "og:image"}),
        ("meta", {"name": "twitter:image"}),
    ]
    for tag_name, attrs in selectors:
        for meta in soup.find_all(tag_name, attrs=attrs):
            content = meta.get("content", "")
            if content:
                url = _resolve_url(content, base_url)
                if url:
                    results.append(ImageTarget(
                        url=url, source_tag="meta-og", original_ref=content,
                    ))
    return results


def _extract_inline_svgs(soup: BeautifulSoup) -> list[ImageTarget]:
    results: list[ImageTarget] = []
    for svg_tag in soup.find_all("svg"):
        if not isinstance(svg_tag, Tag):
            continue
        svg_bytes = serialize_svg_element(svg_tag)
        results.append(ImageTarget(
            url=None,
            source_tag="inline-svg",
            original_ref="<svg>",
            inline_content=svg_bytes,
        ))
    return results


def _resolve_url(ref: str, base_url: str) -> str | None:
    """Resolve a possibly-relative URL reference against a base URL.

    Returns None for data: URIs, fragment-only refs, and unparseable values.
    """
    ref = ref.strip()
    if not ref or ref.startswith("data:") or ref.startswith("#"):
        return None
    try:
        absolute = urljoin(base_url, ref)
    except ValueError:
        return None
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https"):
        return None
    return absolute


def _is_image_url(url: str) -> bool:
    """Check if a URL path ends with a known image extension."""
    parsed = urlparse(url)
    path = parsed.path.lower()
    return any(path.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def _parse_srcset(srcset: str) -> list[str]:
    """Parse a srcset attribute value into a list of URLs."""
    urls: list[str] = []
    for entry in srcset.split(","):
        parts = entry.strip().split()
        if parts:
            urls.append(parts[0])
    return urls


def _deduplicate(targets: list[ImageTarget]) -> list[ImageTarget]:
    """Remove duplicate targets by URL or SVG content hash."""
    seen_urls: set[str] = set()
    seen_svg_hashes: set[str] = set()
    unique: list[ImageTarget] = []
    for t in targets:
        if t.url is not None:
            if t.url in seen_urls:
                continue
            seen_urls.add(t.url)
        else:
            assert t.inline_content is not None
            h = svg_content_hash(t.inline_content)
            if h in seen_svg_hashes:
                continue
            seen_svg_hashes.add(h)
        unique.append(t)
    return unique
