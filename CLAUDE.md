# image-dl

Command-line tool with a terminal UI that downloads all images from a webpage.

## Install

```bash
pip install -e .
```

## Run

```bash
image-dl <url>                      # download to current directory
image-dl <url> -o ./images          # download to specified directory
python -m image_dl <url>            # alternative invocation
```

## CLI Options

- `url` (required) — target webpage URL
- `-o, --output-dir` — download directory (default: `.`)
- `-c, --concurrency` — max concurrent downloads (default: 5)
- `--timeout` — per-request timeout in seconds (default: 30)
- `--no-inline-svg` — skip inline SVG extraction
- `-v, --verbose` — verbose output

## Package Structure

```
src/image_dl/
├── __init__.py       # version, public API
├── __main__.py       # python -m support
├── cli.py            # argument parsing, main entry point
├── scraper.py        # HTML fetching and image URL extraction
├── downloader.py     # async concurrent image downloader
├── models.py         # ImageTarget, DownloadResult dataclasses
├── naming.py         # filename resolution, sanitization, dedup
├── svg.py            # inline SVG serialization
└── tui.py            # Rich-based terminal UI
```

## Dependencies

- **httpx** — HTTP client (sync for page fetch, async for downloads)
- **beautifulsoup4** + **lxml** — HTML parsing
- **rich** — terminal UI (progress bars, live display, tables)

## Supported Image Formats

JPG, PNG, WebP, SVG (files and inline), GIF, BMP, ICO, TIFF, AVIF

## Limitations

- Does not execute JavaScript; only processes raw HTML
- CSS `url()` in `<style>` blocks is not parsed (only inline `style` attributes)
