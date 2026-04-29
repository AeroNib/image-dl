from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Callable

from playwright.async_api import Page, Response, async_playwright

from image_dl.models import CapturedImage
from image_dl.svg import serialize_svg_html, svg_content_hash

IMAGE_CONTENT_TYPES: set[str] = {
    "image/jpeg", "image/png", "image/webp", "image/svg+xml",
    "image/gif", "image/bmp", "image/x-icon", "image/vnd.microsoft.icon",
    "image/tiff", "image/avif",
}

_SCROLL_PAUSE_MS = 300
_SCROLL_STEP_PX = 600


class BrowserError(Exception):
    pass


def _install_chromium(
    on_status: Callable[[str], None] | None = None,
) -> None:
    """Run 'playwright install chromium' to download the browser."""
    if on_status:
        on_status("Installing Chromium browser (first run only)...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise BrowserError(
            "Failed to install Chromium. You can install it manually with:\n"
            "  python -m playwright install chromium"
        ) from exc


async def capture_images(
    url: str,
    timeout: int = 30,
    on_status: Callable[[str], None] | None = None,
) -> list[CapturedImage]:
    """Navigate to a URL with a headless browser and capture all images.

    Uses network interception to capture image responses as the page loads,
    then scrolls the page to trigger lazy-loaded images. Finally, extracts
    inline <svg> elements from the rendered DOM.

    Automatically installs Chromium on first run if not present.
    """
    captured: dict[str, CapturedImage] = {}  # keyed by URL to deduplicate

    async def _on_response(response: Response) -> None:
        content_type = response.headers.get("content-type", "")
        mime = content_type.split(";", 1)[0].strip().lower()
        if mime not in IMAGE_CONTENT_TYPES:
            return
        if response.status < 200 or response.status >= 400:
            return
        resp_url = response.url
        if resp_url in captured:
            return
        try:
            data = await response.body()
            if data:
                captured[resp_url] = CapturedImage(
                    url=resp_url,
                    data=data,
                    content_type=mime,
                    source="network",
                )
        except Exception:
            pass  # response body unavailable (e.g., aborted request)

    if on_status:
        on_status("Launching browser...")

    async with async_playwright() as pw:
        try:
            browser = await pw.chromium.launch(headless=True)
        except Exception:
            # Browser likely not installed — attempt auto-install
            _install_chromium(on_status)
            if on_status:
                on_status("Launching browser...")
            try:
                browser = await pw.chromium.launch(headless=True)
            except Exception as exc:
                raise BrowserError(f"Failed to launch browser: {exc}") from exc

        try:
            page = await browser.new_page()
            page.on("response", _on_response)

            if on_status:
                on_status("Fetching page...")

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            except Exception as exc:
                raise BrowserError(f"Failed to load {url}: {exc}") from exc

            # Wait for initial images to load after DOM is ready
            try:
                await page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass  # Page may never reach networkidle; continue anyway

            if on_status:
                on_status("Scrolling page for lazy-loaded images...")

            await _scroll_page(page)

            # Wait for any remaining network requests triggered by scrolling
            try:
                await page.wait_for_load_state("networkidle", timeout=5_000)
            except Exception:
                pass

            if on_status:
                on_status("Extracting inline SVGs...")

            inline_svgs = await _extract_inline_svgs(page)

        finally:
            await browser.close()

    # Combine network-captured images and inline SVGs
    images = list(captured.values())
    images.extend(inline_svgs)
    return images


async def _scroll_page(page: Page) -> None:
    """Scroll the page from top to bottom to trigger lazy-loaded images."""
    total_height = await page.evaluate("document.body.scrollHeight")
    viewport_height = await page.evaluate("window.innerHeight")
    current = 0

    while current < total_height:
        current += _SCROLL_STEP_PX
        await page.evaluate(f"window.scrollTo(0, {current})")
        await page.wait_for_timeout(_SCROLL_PAUSE_MS)
        # Page may have grown (infinite scroll)
        total_height = await page.evaluate("document.body.scrollHeight")

    # Scroll back to top (some sites load additional content)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(_SCROLL_PAUSE_MS)


async def _extract_inline_svgs(page: Page) -> list[CapturedImage]:
    """Extract inline <svg> elements from the rendered DOM."""
    results: list[CapturedImage] = []
    seen_hashes: set[str] = set()

    svg_elements = await page.query_selector_all("svg")
    for i, el in enumerate(svg_elements):
        try:
            outer_html = await el.evaluate("el => el.outerHTML")
        except Exception:
            continue
        if not outer_html:
            continue

        svg_bytes = serialize_svg_html(outer_html)

        # Deduplicate by content hash
        h = svg_content_hash(svg_bytes)
        if h in seen_hashes:
            continue
        seen_hashes.add(h)

        results.append(CapturedImage(
            url=None,
            data=svg_bytes,
            content_type="image/svg+xml",
            source="inline-svg",
        ))
    return results
