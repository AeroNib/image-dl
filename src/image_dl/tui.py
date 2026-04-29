from __future__ import annotations

from collections import deque

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

from image_dl.models import DownloadResult


def _format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    else:
        return f"{n / (1024 * 1024):.1f} MB"


class DownloadTUI:
    """Rich-based terminal UI for image-dl."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()
        self._phase = ""
        self._total = 0
        self._completed = 0
        self._failed = 0
        self._skipped = 0
        self._bytes_downloaded = 0
        self._log: deque[str] = deque(maxlen=10)
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
        )
        self._task_id: int | None = None
        self._live: Live | None = None

    def start(self) -> None:
        self._live = Live(
            self._build_display(),
            console=self.console,
            refresh_per_second=10,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live:
            self._live.stop()
            self._live = None

    def set_total(self, total: int) -> None:
        self._total = total
        if self._task_id is not None:
            self._progress.update(self._task_id, total=total)

    def update_phase(self, phase: str) -> None:
        self._phase = phase
        self._refresh()

    def begin_downloads(self, total: int) -> None:
        self._total = total
        self._task_id = self._progress.add_task("Downloading", total=total)
        self._refresh()

    def on_download_complete(self, result: DownloadResult) -> None:
        if result.status == "ok":
            self._completed += 1
            self._bytes_downloaded += result.size_bytes
            name = result.filepath.name if result.filepath else "?"
            size = _format_bytes(result.size_bytes)
            self._log.append(f"[green]  {name}[/]  ({size})")
        elif result.status == "skipped":
            self._skipped += 1
            ref = result.target.original_ref[:60]
            reason = result.error or "skipped"
            self._log.append(f"[yellow]  {ref}[/]  ({reason})")
        else:
            self._failed += 1
            ref = result.target.original_ref[:60]
            reason = result.error or "error"
            self._log.append(f"[red]  {ref}[/]  ({reason})")

        if self._task_id is not None:
            self._progress.advance(self._task_id, advance=result.size_bytes)

        self._refresh()

    def show_summary(self, results: list[DownloadResult]) -> None:
        self.stop()

        table = Table(title="Download Summary", show_lines=False)
        table.add_column("Metric", style="bold")
        table.add_column("Value", justify="right")
        table.add_row("Total images found", str(self._total))
        table.add_row("Downloaded", f"[green]{self._completed}[/]")
        table.add_row("Skipped", f"[yellow]{self._skipped}[/]")
        table.add_row("Failed", f"[red]{self._failed}[/]")
        table.add_row("Total size", _format_bytes(self._bytes_downloaded))
        self.console.print()
        self.console.print(table)

        errors = [r for r in results if r.status == "error"]
        if errors:
            self.console.print()
            self.console.print("[bold red]Errors:[/]")
            for r in errors:
                ref = r.target.original_ref[:80]
                self.console.print(f"  {ref} - {r.error}")

    def show_error(self, message: str) -> None:
        self.stop()
        self.console.print(Panel(
            f"[bold red]{message}[/]",
            title="Error",
            border_style="red",
        ))

    def _build_display(self) -> Table:
        grid = Table.grid(padding=(0, 0))
        grid.add_row(
            Panel(
                Text(f"image-dl   {self._phase}", style="bold cyan"),
                border_style="cyan",
            )
        )

        if self._task_id is not None:
            grid.add_row(self._progress)

            stats = Text()
            stats.append(f"  {_format_bytes(self._bytes_downloaded)}", style="bold")
            stats.append(f"   {self._completed}", style="green")
            stats.append(f"   {self._failed}", style="red")
            if self._skipped:
                stats.append(f"   {self._skipped}", style="yellow")
            grid.add_row(stats)

        if self._log:
            log_text = Text()
            for i, line in enumerate(self._log):
                if i > 0:
                    log_text.append("\n")
                log_text.append_text(Text.from_markup(line))
            grid.add_row(Panel(log_text, title="Recent", border_style="dim"))

        return grid

    def _refresh(self) -> None:
        if self._live:
            self._live.update(self._build_display())
