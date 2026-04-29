from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from image_dl.models import CapturedImage, SaveResult
from image_dl.naming import resolve_filename
from image_dl.svg import generate_svg_filename


def save_all(
    images: list[CapturedImage],
    output_dir: Path,
    progress_callback: Callable[[SaveResult], None] | None = None,
) -> list[SaveResult]:
    """Save all captured images to disk.

    Images already have their data in memory (from network interception or
    inline SVG extraction), so this is purely a disk-write operation.
    """
    used_names: set[str] = set()
    results: list[SaveResult] = []
    svg_index = 0

    for image in images:
        result = _save_one(image, output_dir, used_names, svg_index)
        if image.source == "inline-svg":
            svg_index += 1
        results.append(result)
        if progress_callback:
            progress_callback(result)

    return results


def _save_one(
    image: CapturedImage,
    output_dir: Path,
    used_names: set[str],
    svg_index: int,
) -> SaveResult:
    """Save a single image to disk."""
    try:
        if image.source == "inline-svg":
            filename = generate_svg_filename(image.data, svg_index)
            from image_dl.naming import deduplicate_filename
            filename = deduplicate_filename(filename, used_names)
            used_names.add(filename)
        else:
            filename = resolve_filename(
                image.url, image.content_type, None, used_names,
            )

        filepath = output_dir / filename
        filepath.write_bytes(image.data)

        return SaveResult(
            image=image,
            filepath=filepath,
            status="ok",
            size_bytes=len(image.data),
        )
    except OSError as exc:
        return SaveResult(
            image=image,
            status="error",
            error=f"Write error: {exc}",
        )
