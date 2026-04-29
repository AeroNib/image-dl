# image-dl

Command-line tool with a terminal UI that downloads all images from a webpage.
Uses a headless browser (Playwright) to capture dynamically loaded images.

## Install

```bash
pipx install git+https://github.com/AeroNib/image-dl.git
```

Chromium is automatically downloaded on first run. For local development:

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
- `--timeout` — page load timeout in seconds (default: 30)
- `--no-inline-svg` — skip inline SVG extraction
- `-v, --verbose` — verbose output

## Package Structure

```
src/image_dl/
├── __init__.py       # version, public API
├── __main__.py       # python -m support
├── cli.py            # argument parsing, main entry point
├── browser.py        # Playwright headless browser, network interception, scrolling
├── downloader.py     # save captured images to disk
├── models.py         # CapturedImage, SaveResult dataclasses
├── naming.py         # filename resolution, sanitization, dedup
├── svg.py            # inline SVG serialization
└── tui.py            # Rich-based terminal UI
```

## Dependencies

- **playwright** — headless browser for page rendering, JS execution, and network interception
- **rich** — terminal UI (progress bars, live display, tables)

## How It Works

1. Launches a headless Chromium browser via Playwright
2. Listens for network responses with image content-types (captures bytes in memory)
3. Navigates to the target URL, waits for network idle
4. Scrolls the page top-to-bottom to trigger lazy-loaded images
5. Extracts inline `<svg>` elements from the rendered DOM
6. Saves all captured images to disk

## Supported Image Formats

JPG, PNG, WebP, SVG (files and inline), GIF, BMP, ICO, TIFF, AVIF
