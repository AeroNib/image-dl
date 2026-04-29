from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path

import httpx

from image_dl.models import DownloadResult, ImageTarget
from image_dl.naming import resolve_filename
from image_dl.scraper import IMAGE_CONTENT_TYPES
from image_dl.svg import generate_svg_filename

DEFAULT_CONCURRENCY = 5
_DEFAULT_USER_AGENT = "image-dl/0.1 (https://github.com/image-dl)"
_CHUNK_SIZE = 8192


async def download_all(
    targets: list[ImageTarget],
    output_dir: Path,
    concurrency: int = DEFAULT_CONCURRENCY,
    timeout: int = 30,
    user_agent: str | None = None,
    progress_callback: Callable[[DownloadResult], None] | None = None,
) -> list[DownloadResult]:
    """Download all image targets concurrently.

    Returns a list of DownloadResult in the same order as targets.
    Calls progress_callback after each download completes.
    """
    semaphore = asyncio.Semaphore(concurrency)
    used_names: set[str] = set()
    results: list[DownloadResult] = []
    lock = asyncio.Lock()

    headers = {"User-Agent": user_agent or _DEFAULT_USER_AGENT}

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
    ) as client:
        tasks: list[asyncio.Task[DownloadResult]] = []
        for i, target in enumerate(targets):
            if target.inline_content is not None:
                task = asyncio.create_task(
                    _save_inline_svg(target, output_dir, used_names, i, lock)
                )
            else:
                task = asyncio.create_task(
                    _download_one(client, target, output_dir, semaphore, used_names, lock)
                )
            tasks.append(task)

        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            if progress_callback:
                progress_callback(result)

    return results


async def _download_one(
    client: httpx.AsyncClient,
    target: ImageTarget,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
    used_names: set[str],
    lock: asyncio.Lock,
) -> DownloadResult:
    """Download a single image URL to disk."""
    assert target.url is not None
    try:
        async with semaphore:
            response = await client.get(target.url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            mime = content_type.split(";", 1)[0].strip().lower()

            # Validate it's actually an image
            if mime and mime not in IMAGE_CONTENT_TYPES and not mime.startswith("image/"):
                return DownloadResult(
                    target=target,
                    status="skipped",
                    error=f"Not an image (content-type: {mime})",
                )

            async with lock:
                filename = resolve_filename(
                    target.url, content_type, None, used_names,
                )

            filepath = output_dir / filename
            data = response.content
            filepath.write_bytes(data)

            return DownloadResult(
                target=target,
                filepath=filepath,
                status="ok",
                size_bytes=len(data),
            )
    except httpx.TimeoutException:
        return DownloadResult(
            target=target, status="error", error="Timeout",
        )
    except httpx.HTTPStatusError as exc:
        return DownloadResult(
            target=target, status="error",
            error=f"HTTP {exc.response.status_code}",
        )
    except httpx.HTTPError as exc:
        return DownloadResult(
            target=target, status="error", error=str(exc),
        )
    except OSError as exc:
        return DownloadResult(
            target=target, status="error", error=f"Write error: {exc}",
        )


async def _save_inline_svg(
    target: ImageTarget,
    output_dir: Path,
    used_names: set[str],
    index: int,
    lock: asyncio.Lock,
) -> DownloadResult:
    """Write an inline SVG's content directly to disk."""
    assert target.inline_content is not None
    try:
        svg_name = generate_svg_filename(target.inline_content, index)

        async with lock:
            # Deduplicate against other filenames
            from image_dl.naming import deduplicate_filename
            final_name = deduplicate_filename(svg_name, used_names)
            used_names.add(final_name)

        filepath = output_dir / final_name
        filepath.write_bytes(target.inline_content)

        return DownloadResult(
            target=target,
            filepath=filepath,
            status="ok",
            size_bytes=len(target.inline_content),
        )
    except OSError as exc:
        return DownloadResult(
            target=target, status="error", error=f"Write error: {exc}",
        )
