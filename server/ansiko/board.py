"""Board layout and frame composition.

A board either lists widget directory names (automatic packing) or explicit
cells with fractional coordinates for a fixed composition:

    name = "default"
    frame = true

    [[cells]]
    widget = "ttyclock"
    x = 0.0
    y = 0.0
    width = 0.5
    height = 1.0
"""

from __future__ import annotations

import asyncio
import re
import tomllib
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .widgets import Widget, load_widget, run_widget

BOARD_MANIFEST = "board.toml"
BORDER = "\x1b[36m"
RESET = "\x1b[0m"


@dataclass(frozen=True)
class Region:
    x: float
    y: float
    width: float
    height: float
    frame: bool


@dataclass(frozen=True)
class BoardSpec:
    name: str
    widgets: list[Widget]
    regions: list[Region] | None = None
    frame: bool = False


@dataclass
class Cell:
    widget: Widget
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    frame: bool = False
    output: str = ""
    error: str | None = None

    def __post_init__(self) -> None:
        if self.width <= 0:
            self.width = self.widget.width
        if self.height <= 0:
            self.height = self.widget.height

    @property
    def framed(self) -> bool:
        return self.frame and self.width >= 3 and self.height >= 3

    @property
    def content_width(self) -> int:
        return self.width - 2 if self.framed else self.width

    @property
    def content_height(self) -> int:
        return self.height - 2 if self.framed else self.height


def place(cells: Sequence[Cell], cols: int, rows: int) -> None:
    """Pack cells left-to-right, wrapping to a new row. Off-screen cells get -1."""
    x = y = row_height = 0
    for cell in cells:
        if x > 0 and x + cell.width > cols:
            x = 0
            y += row_height + 1
            row_height = 0
        if y >= rows:
            cell.x = cell.y = -1
            continue
        cell.x, cell.y = x, y
        x += cell.width + 1
        row_height = max(row_height, cell.height)


def place_regions(
    cells: Sequence[Cell], regions: Sequence[Region], cols: int, rows: int
) -> None:
    for cell, region in zip(cells, regions, strict=True):
        x0 = min(cols - 1, round(region.x * cols))
        y0 = min(rows - 1, round(region.y * rows))
        x1 = max(x0 + 1, round((region.x + region.width) * cols))
        y1 = max(y0 + 1, round((region.y + region.height) * rows))
        cell.x, cell.y = x0, y0
        cell.width = x1 - x0
        cell.height = y1 - y0
        cell.frame = region.frame


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


def _cursor(row: int, col: int) -> bytes:
    return f"\x1b[{row};{col}H".encode()


def _frame_top(cell: Cell) -> str:
    inner = cell.width - 2
    title = f" {cell.widget.name} "
    if len(title) > inner:
        title = ""
    return "┌" + title + "─" * (inner - len(title)) + "┐"


def compose(cells: Sequence[Cell], rows: int) -> bytes:
    chunks = [b"\x1b[2J\x1b[H\x1b[?25l"]
    for cell in cells:
        if cell.x < 0 or cell.y < 0 or cell.y >= rows:
            continue

        if cell.framed and cell.y + cell.height <= rows:
            inner = cell.width - 2
            chunks.append(_cursor(cell.y + 1, cell.x + 1))
            chunks.append((BORDER + _frame_top(cell) + RESET).encode())
            for offset in range(1, cell.height - 1):
                chunks.append(_cursor(cell.y + offset + 1, cell.x + 1))
                chunks.append((BORDER + "│" + RESET).encode())
                chunks.append(_cursor(cell.y + offset + 1, cell.x + cell.width))
                chunks.append((BORDER + "│" + RESET).encode())
            chunks.append(_cursor(cell.y + cell.height, cell.x + 1))
            chunks.append((BORDER + "└" + "─" * inner + "┘" + RESET).encode())

        if cell.error:
            first_line = cell.error.splitlines()[0] if cell.error.splitlines() else ""
            text = f"! {cell.widget.name}: {first_line}"
        else:
            text = cell.output

        content_x = cell.x + (1 if cell.framed else 0)
        content_y = cell.y + (1 if cell.framed else 0)
        max_lines = max(0, min(cell.content_height, rows - content_y))
        lines = text.splitlines()[:max_lines]
        for index, line in enumerate(lines):
            chunks.append(_cursor(content_y + index + 1, content_x + 1))
            chunks.append(_clip(line.replace("\r", ""), cell.content_width).encode())
            chunks.append(RESET.encode())
    return b"".join(chunks)


def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError(f"invalid name: {value!r}")
    return value


def _fraction(data: dict, key: str) -> float:
    if key not in data:
        raise ValueError(f"board cell: missing {key!r}")
    value = data[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"board cell: {key!r} must be a number")
    value = float(value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"board cell: {key!r} must be between 0 and 1")
    return value


def _board_data(data: object, name: str, widgets_dir: Path) -> BoardSpec:
    if not isinstance(data, dict):
        raise TypeError("invalid board")

    title = data.get("name", name)
    if not isinstance(title, str) or not title.strip():
        raise ValueError("board: 'name' must be a non-empty string")

    frame = data.get("frame", False)
    if not isinstance(frame, bool):
        raise TypeError("board: 'frame' must be a boolean")

    if "cells" in data:
        if "widgets" in data:
            raise ValueError("board: use either 'cells' or 'widgets', not both")
        entries = data["cells"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("board: 'cells' must be a non-empty list")
        widgets: list[Widget] = []
        regions: list[Region] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("board: each cell must be a table")
            widget_name = entry.get("widget")
            if not isinstance(widget_name, str) or not widget_name:
                raise ValueError("board cell: missing 'widget'")
            x = _fraction(entry, "x")
            y = _fraction(entry, "y")
            width = _fraction(entry, "width")
            height = _fraction(entry, "height")
            if width <= 0 or height <= 0:
                raise ValueError("board cell: width and height must be positive")
            if x + width > 1.0001 or y + height > 1.0001:
                raise ValueError("board cell: cell extends beyond the display")
            cell_frame = entry.get("frame", frame)
            if not isinstance(cell_frame, bool):
                raise TypeError("board cell: 'frame' must be a boolean")
            widgets.append(load_widget(widgets_dir / safe_name(widget_name)))
            regions.append(Region(x, y, width, height, cell_frame))
        return BoardSpec(title.strip(), widgets, regions, frame)

    names = data.get("widgets")
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(item, str) and item for item in names)
    ):
        raise ValueError("board: 'widgets' must be a non-empty list of names")

    widgets = [
        load_widget(widgets_dir / safe_name(widget_name)) for widget_name in names
    ]
    return BoardSpec(title.strip(), widgets, None, frame)


def load_board(name: str, boards_dir: Path, widgets_dir: Path) -> BoardSpec:
    safe_name(name)
    board_file = boards_dir / name / BOARD_MANIFEST
    if not board_file.is_file():
        raise FileNotFoundError(f"board not found: {name}")

    with board_file.open("rb") as f:
        data = tomllib.load(f)
    return _board_data(data, name, widgets_dir)


def parse_board_source(text: str, name: str, widgets_dir: Path) -> BoardSpec:
    data = tomllib.loads(text)
    return _board_data(data, name, widgets_dir)


def list_boards(boards_dir: Path) -> list[str]:
    if not boards_dir.is_dir():
        return []
    return sorted(
        path.name for path in boards_dir.iterdir() if (path / BOARD_MANIFEST).is_file()
    )


def read_board_source(name: str, boards_dir: Path) -> str:
    safe_name(name)
    path = boards_dir / name / BOARD_MANIFEST
    if not path.is_file():
        raise FileNotFoundError(f"board not found: {name}")
    return path.read_text(encoding="utf-8")


def save_board_source(name: str, text: str, boards_dir: Path, widgets_dir: Path) -> str:
    safe_name(name)
    path = boards_dir / name / BOARD_MANIFEST
    if not path.is_file():
        raise FileNotFoundError(f"board not found: {name}")
    spec = parse_board_source(text, name, widgets_dir)
    path.write_text(text, encoding="utf-8")
    return spec.name


def create_board(name: str, boards_dir: Path) -> None:
    safe_name(name)
    path = boards_dir / name / BOARD_MANIFEST
    if path.exists():
        raise FileExistsError(f"board already exists: {name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'name = "{name}"\nwidgets = ["clock"]\n', encoding="utf-8")


class Board:
    def __init__(
        self,
        name: str,
        widgets: Sequence[Widget],
        cols: int,
        rows: int,
        emit: Callable[[bytes], None],
        regions: Sequence[Region] | None = None,
        frame: bool = False,
    ) -> None:
        self.name = name
        self.cols = cols
        self.rows = rows
        self.emit = emit
        self.regions = regions
        if regions is None:
            self.cells = [
                Cell(
                    widget,
                    width=widget.width + (2 if frame else 0),
                    height=widget.height + (2 if frame else 0),
                    frame=frame,
                )
                for widget in widgets
            ]
            place(self.cells, cols, rows)
        else:
            if len(widgets) != len(regions):
                raise ValueError("board: widgets and regions differ")
            self.cells = [
                Cell(widget, frame=region.frame)
                for widget, region in zip(widgets, regions, strict=True)
            ]
            place_regions(self.cells, regions, cols, rows)

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
        if self.regions is None:
            place(self.cells, cols, rows)
        else:
            place_regions(self.cells, self.regions, cols, rows)
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
                cell.output, cell.error = await run_widget(
                    cell.widget, cell.content_width, cell.content_height
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - isolate every widget
                cell.output, cell.error = "", f"{type(e).__name__}: {e}"
            self._dirty.set()
            await asyncio.sleep(max(0.1, cell.widget.interval))
