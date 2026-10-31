"""Board grid layout and frame composition.

A board is a TOML file that lists widget directory names. Cells are packed
left-to-right and wrapped by row; there are no coordinates or editor yet.
"""

from __future__ import annotations

import asyncio
import tomllib
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .widgets import Widget, load_widget, run_widget

BOARD_MANIFEST = "board.toml"


@dataclass
class Cell:
    widget: Widget
    x: int = 0
    y: int = 0
    output: str = ""
    error: str | None = None


def place(cells: Sequence[Cell], cols: int, rows: int) -> None:
    """Pack cells left-to-right, wrapping to a new row. Off-screen cells get -1."""
    x = y = row_height = 0
    for cell in cells:
        widget = cell.widget
        if x > 0 and x + widget.width > cols:
            x = 0
            y += row_height + 1
            row_height = 0
        if y >= rows:
            cell.x = cell.y = -1
            continue
        cell.x, cell.y = x, y
        x += widget.width + 1
        row_height = max(row_height, widget.height)


def _clip(text: str, width: int) -> str:
    """Keep the first `width` terminal columns, preserving ANSI sequences."""
    out: list[str] = []
    used = 0
    i = 0
    while i < len(text) and used < width:
        ch = text[i]
        if ch == "\x1b" and i + 1 < len(text):
            if text[i + 1] == "[":
                j = i + 2
                while j < len(text) and not ("@" <= text[j] <= "~"):
                    j += 1
                j = min(j + 1, len(text))
                out.append(text[i:j])
                i = j
                continue
            if text[i + 1] == "]":
                j = i + 2
                while j < len(text):
                    if text[j] == "\a":
                        j += 1
                        break
                    if text[j] == "\x1b" and j + 1 < len(text) and text[j + 1] == "\\":
                        j += 2
                        break
                    j += 1
                out.append(text[i:j])
                i = j
                continue

        if unicodedata.combining(ch):
            cell_width = 0
        elif unicodedata.east_asian_width(ch) in ("W", "F"):
            cell_width = 2
        else:
            cell_width = 1
        if used + cell_width > width:
            break
        out.append(ch)
        used += cell_width
        i += 1
    return "".join(out)


def compose(cells: Sequence[Cell], rows: int) -> bytes:
    chunks = [b"\x1b[2J\x1b[H\x1b[?25l"]
    for cell in cells:
        if cell.x < 0 or cell.y < 0 or cell.y >= rows:
            continue
        if cell.error:
            first_line = cell.error.splitlines()[0] if cell.error.splitlines() else ""
            text = f"! {cell.widget.name}: {first_line}"
        else:
            text = cell.output
        lines = text.splitlines()[: max(0, min(cell.widget.height, rows - cell.y))]
        for index, line in enumerate(lines):
            row, col = cell.y + index + 1, cell.x + 1
            chunks.append(f"\x1b[{row};{col}H".encode())
            chunks.append(_clip(line.replace("\r", ""), cell.widget.width).encode())
            chunks.append(b"\x1b[0m")
    return b"".join(chunks)


def _safe_component(value: str) -> str:
    if not value or value in (".", "..") or "/" in value or "\\" in value:
        raise ValueError(f"invalid name: {value!r}")
    return value


def load_board(
    name: str, boards_dir: Path, widgets_dir: Path
) -> tuple[str, list[Widget]]:
    _safe_component(name)
    board_file = boards_dir / name / BOARD_MANIFEST
    if not board_file.is_file():
        raise FileNotFoundError(f"board not found: {name}")

    with board_file.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"invalid board: {board_file}")

    title = data.get("name", name)
    if not isinstance(title, str) or not title.strip():
        raise ValueError("board: 'name' must be a non-empty string")

    names = data.get("widgets")
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(item, str) and item for item in names)
    ):
        raise ValueError("board: 'widgets' must be a non-empty list of names")

    widgets = [
        load_widget(widgets_dir / _safe_component(widget_name)) for widget_name in names
    ]
    return title.strip(), widgets


class Board:
    def __init__(
        self,
        name: str,
        widgets: Sequence[Widget],
        cols: int,
        rows: int,
        emit: Callable[[bytes], None],
    ) -> None:
        self.name = name
        self.cols = cols
        self.rows = rows
        self.emit = emit
        self.cells = [Cell(widget) for widget in widgets]
        place(self.cells, cols, rows)

        self._dirty = asyncio.Event()
        self._render_task: asyncio.Task | None = None
        self._widget_tasks: list[asyncio.Task] = []
        self._stopped = False

    def start(self) -> None:
        self._render_task = asyncio.create_task(self._render_loop())
        self._widget_tasks = [
            asyncio.create_task(self._widget_loop(cell)) for cell in self.cells
        ]
        self._dirty.set()

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        for task in (self._render_task, *self._widget_tasks):
            if task is not None:
                task.cancel()

    def set_size(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        place(self.cells, cols, rows)
        self._dirty.set()

    def request_render(self) -> None:
        self._dirty.set()

    async def _render_loop(self) -> None:
        while not self._stopped:
            await self._dirty.wait()
            self._dirty.clear()
            if self._stopped:
                return
            self.emit(compose(self.cells, self.rows))

    async def _widget_loop(self, cell: Cell) -> None:
        while not self._stopped:
            try:
                cell.output, cell.error = await run_widget(cell.widget)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - isolate every widget
                cell.output, cell.error = "", f"{type(e).__name__}: {e}"
            self._dirty.set()
            await asyncio.sleep(max(0.1, cell.widget.interval))
