from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse

from image_dl import __version__
from image_dl.downloader import download_all
from image_dl.scraper import ScraperError, extract_images, fetch_page
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
        "-c", "--concurrency",
        type=int, default=5,
        help="Max concurrent downloads (default: 5)",
    )
    parser.add_argument(
        "--timeout",
        type=int, default=30,
        help="Per-request timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--no-inline-svg",
        action="store_true",
        help="Skip extraction of inline SVG elements",
    )
    parser.add_argument(
        "--user-agent",
        default=None,
        help="Custom User-Agent header",
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

    # Fetch the page
    tui.update_phase("Fetching page...")
    try:
        html, final_url = fetch_page(
            url, timeout=args.timeout, user_agent=args.user_agent,
        )
    except ScraperError as exc:
        tui.show_error(str(exc))
        return 2

    # Extract image targets
    tui.update_phase("Extracting images...")
    include_inline_svg = not args.no_inline_svg
    targets = extract_images(html, final_url, include_inline_svg=include_inline_svg)

    if not targets:
        tui.stop()
        tui.console.print("[yellow]No images found on this page.[/]")
        return 0

    # Download
    tui.update_phase(f"Downloading {len(targets)} images...")
    tui.begin_downloads(total=len(targets))

    results = asyncio.run(download_all(
        targets=targets,
        output_dir=output_dir,
        concurrency=args.concurrency,
        timeout=args.timeout,
        user_agent=args.user_agent,
        progress_callback=tui.on_download_complete,
    ))

    # Summary
    tui.show_summary(results)

    # Exit code
    errors = [r for r in results if r.status == "error"]
    if len(errors) == len(results):
        return 2  # all failed
    elif errors:
        return 1  # partial failure
    return 0
