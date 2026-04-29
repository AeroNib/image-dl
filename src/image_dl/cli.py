from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from urllib.parse import urlparse

from image_dl import __version__
from image_dl.browser import BrowserError, capture_images
from image_dl.downloader import save_all
from image_dl.tui import DownloadTUI


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="image-dl",
        description="Download all images from a webpage.",
    )
    parser.add_argument("url", help="URL of the webpage to download images from")
    parser.add_argument(
        "-o", "--output-dir",
        default=".",
        help="Directory to save images to (default: current directory)",
    )
    parser.add_argument(
        "--timeout",
        type=int, default=30,
        help="Page load timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--no-inline-svg",
        action="store_true",
        help="Skip extraction of inline SVG elements",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(argv)


def _validate_url(url: str) -> str:
    """Basic URL validation. Prepend https:// if no scheme provided."""
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")
    return url


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    tui = DownloadTUI()

    try:
        url = _validate_url(args.url)
    except ValueError as exc:
        tui.show_error(str(exc))
        return 2

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    tui.start()

    # Capture images using headless browser
    try:
        images = asyncio.run(capture_images(
            url,
            timeout=args.timeout,
            on_status=tui.update_phase,
        ))
    except BrowserError as exc:
        tui.show_error(str(exc))
        return 2

    # Filter out inline SVGs if requested
    if args.no_inline_svg:
        images = [img for img in images if img.source != "inline-svg"]

    if not images:
        tui.stop()
        tui.console.print("[yellow]No images found on this page.[/]")
        return 0

    # Save to disk
    tui.update_phase(f"Saving {len(images)} images...")
    tui.begin_downloads(total=len(images))

    results = save_all(
        images=images,
        output_dir=output_dir,
        progress_callback=tui.on_download_complete,
    )

    # Summary
    tui.show_summary(results)

    # Exit code
    errors = [r for r in results if r.status == "error"]
    if len(errors) == len(results):
        return 2
    elif errors:
        return 1
    return 0
