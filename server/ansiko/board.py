"""Board layout, validation, persistence, and frame composition.

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
import math
import os
import re
import shutil
import tempfile
import tomllib
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .config import DEFAULT_BOARDS, PACKAGE_RESOURCES, default_dir
from .widgets import Widget, resolve_widget, run_widget, scan_widgets

BOARD_MANIFEST = "board.toml"
BORDER = "\x1b[36m"
CUSTOM_SOURCE = "custom"
BUNDLED_SOURCE = "bundled"
RESET = "\x1b[0m"
TEMPLATES = ("auto", "single", "columns", "grid")
ALIGNS = ("left", "center", "right")
VALIGNS = ("top", "center", "bottom")


@dataclass(frozen=True)
class Region:
    x: float
    y: float
    width: float
    height: float
    frame: bool
    frame_override: bool | None = None
    align: str = "left"
    valign: str = "top"


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
    align: str = "left"
    valign: str = "top"
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
        cell.width, cell.height = x1 - x0, y1 - y0
        cell.frame = region.frame
        cell.align = region.align
        cell.valign = region.valign


def _ansi_end(text: str, i: int) -> int | None:
    """End of the ANSI sequence at `text[i]`, or None if there is no sequence there."""
    if text[i] != "\x1b" or i + 1 >= len(text):
        return None
    if text[i + 1] == "[":
        j = i + 2
        while j < len(text) and not ("@" <= text[j] <= "~"):
            j += 1
        return min(j + 1, len(text))
    if text[i + 1] == "]":
        j = i + 2
        while j < len(text):
            if text[j] == "\a":
                return j + 1
            if text[j] == "\x1b" and j + 1 < len(text) and text[j + 1] == "\\":
                return j + 2
            j += 1
        return j
    return None


def _char_width(ch: str) -> int:
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


def _text_width(text: str) -> int:
    used = 0
    i = 0
    while i < len(text):
        end = _ansi_end(text, i)
        if end is not None:
            i = end
            continue
        used += _char_width(text[i])
        i += 1
    return used


def _clip(text: str, width: int) -> str:
    """Keep the first `width` terminal columns, preserving ANSI sequences."""
    out: list[str] = []
    used = 0
    i = 0
    while i < len(text) and used < width:
        end = _ansi_end(text, i)
        if end is not None:
            out.append(text[i:end])
            i = end
            continue

        cell_width = _char_width(text[i])
        if used + cell_width > width:
            break
        out.append(text[i])
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
        if cell.valign == "bottom":
            content_y += max(0, max_lines - len(lines))
        elif cell.valign == "center":
            content_y += max(0, (max_lines - len(lines)) // 2)
        for index, line in enumerate(lines):
            line = line.replace("\r", "")
            padding = cell.content_width - _text_width(line)
            if cell.align == "right":
                padding = max(0, padding)
            elif cell.align == "center":
                padding = max(0, padding // 2)
            else:
                padding = 0
            chunks.append(_cursor(content_y + index + 1, content_x + padding + 1))
            chunks.append(_clip(line, cell.content_width).encode())
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


def _board_data(
    data: object, name: str, widgets_dir: Path, custom_widgets_dir: Path | None = None
) -> BoardSpec:
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
            overridden = entry.get("frame")
            if overridden is not None and not isinstance(overridden, bool):
                raise TypeError("board cell: 'frame' must be a boolean")
            align = entry.get("align", "left")
            if align not in ALIGNS:
                raise ValueError(f"board cell: 'align' must be one of {ALIGNS}")
            valign = entry.get("valign", "top")
            if valign not in VALIGNS:
                raise ValueError(f"board cell: 'valign' must be one of {VALIGNS}")
            cell_frame = frame if overridden is None else overridden
            widgets.append(
                resolve_widget(safe_name(widget_name), widgets_dir, custom_widgets_dir)
            )
            regions.append(
                Region(x, y, width, height, cell_frame, overridden, align, valign)
            )
        return BoardSpec(title.strip(), widgets, regions, frame)

    names = data.get("widgets")
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(item, str) and item for item in names)
    ):
        raise ValueError("board: 'widgets' must be a non-empty list of names")

    widgets = [
        resolve_widget(safe_name(widget_name), widgets_dir, custom_widgets_dir)
        for widget_name in names
    ]
    return BoardSpec(title.strip(), widgets, None, frame)


def _board_roots(
    boards_dir: Path, custom_boards_dir: Path | None = None
) -> list[tuple[Path, str]]:
    roots: list[tuple[Path, str]] = []
    if custom_boards_dir is not None:
        roots.append((custom_boards_dir, CUSTOM_SOURCE))
    roots.append((boards_dir, BUNDLED_SOURCE))
    return roots


def _find_board(
    name: str, boards_dir: Path, custom_boards_dir: Path | None = None
) -> tuple[Path, str]:
    safe_name(name)
    for root, source in _board_roots(boards_dir, custom_boards_dir):
        if (root / name / BOARD_MANIFEST).is_file():
            return root, source
    raise FileNotFoundError(f"board not found: {name}")


def _board_exists(
    name: str, boards_dir: Path, custom_boards_dir: Path | None = None
) -> bool:
    try:
        _find_board(name, boards_dir, custom_boards_dir)
        return True
    except FileNotFoundError:
        return False


def _write_board_root(boards_dir: Path, custom_boards_dir: Path | None = None) -> Path:
    if custom_boards_dir is not None and custom_boards_dir != boards_dir:
        return custom_boards_dir
    return boards_dir


def _is_bundled_root(boards_dir: Path) -> bool:
    """True for the repository/package example directory, not a user data dir."""
    bundled = {
        default_dir(DEFAULT_BOARDS).resolve(),
        (PACKAGE_RESOURCES / DEFAULT_BOARDS).resolve(),
    }
    return boards_dir.resolve() in bundled


def load_board(
    name: str,
    boards_dir: Path,
    widgets_dir: Path,
    custom_widgets_dir: Path | None = None,
    custom_boards_dir: Path | None = None,
) -> BoardSpec:
    root, _ = _find_board(name, boards_dir, custom_boards_dir)
    with (root / name / BOARD_MANIFEST).open("rb") as f:
        data = tomllib.load(f)
    return _board_data(data, name, widgets_dir, custom_widgets_dir)


def parse_board_source(
    text: str,
    name: str,
    widgets_dir: Path,
    custom_widgets_dir: Path | None = None,
) -> BoardSpec:
    data = tomllib.loads(text)
    return _board_data(data, name, widgets_dir, custom_widgets_dir)


def board_to_model(spec: BoardSpec, folder: str | None = None) -> dict:
    model: dict = {
        "name": spec.name,
        "folder": folder,
        "frame": spec.frame,
        "mode": "auto" if spec.regions is None else "cells",
    }
    if spec.regions is None:
        model["widgets"] = [widget.id for widget in spec.widgets]
        model["cells"] = []
    else:
        model["widgets"] = []
        model["cells"] = [
            {
                "widget": widget.id,
                "x": region.x,
                "y": region.y,
                "width": region.width,
                "height": region.height,
                "frame": region.frame,
                "frame_override": region.frame_override,
                "align": region.align,
                "valign": region.valign,
            }
            for widget, region in zip(spec.widgets, spec.regions, strict=True)
        ]
    return model


def _toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def source_from_model(model: dict) -> str:
    """Serialize a board model produced by the web editor or templates."""
    title = model.get("name")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("board: 'name' must be a non-empty string")
    frame = model.get("frame", False)
    if not isinstance(frame, bool):
        raise TypeError("board: 'frame' must be a boolean")
    mode = model.get("mode", "cells")
    if mode not in ("auto", "cells"):
        raise ValueError("board: 'mode' must be 'auto' or 'cells'")

    lines = [
        f"name = {_toml_string(title.strip())}",
        f"frame = {'true' if frame else 'false'}",
    ]
    if mode == "auto":
        widgets = model.get("widgets")
        if (
            not isinstance(widgets, list)
            or not widgets
            or not all(isinstance(item, str) and item for item in widgets)
        ):
            raise ValueError("board: 'widgets' must be a non-empty list of names")
        items = ", ".join(_toml_string(item) for item in widgets)
        lines.append(f"widgets = [{items}]")
        return "\n".join(lines) + "\n"

    cells = model.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError("board: 'cells' must be a non-empty list")
    for cell in cells:
        if not isinstance(cell, dict):
            raise TypeError("board: each cell must be a table")
        widget = cell.get("widget")
        if not isinstance(widget, str) or not widget:
            raise ValueError("board cell: missing 'widget'")
        x, y, width, height = (
            _fraction(cell, key) for key in ("x", "y", "width", "height")
        )
        if width <= 0 or height <= 0:
            raise ValueError("board cell: width and height must be positive")
        lines.extend(
            [
                "",
                "[[cells]]",
                f"widget = {_toml_string(widget)}",
                f"x = {x:g}",
                f"y = {y:g}",
                f"width = {width:g}",
                f"height = {height:g}",
            ]
        )
        cell_frame = cell.get("frame")
        if isinstance(cell_frame, bool) and cell_frame != frame:
            lines.append(f"frame = {'true' if cell_frame else 'false'}")
        align = cell.get("align", "left")
        if align != "left":
            if align not in ALIGNS:
                raise ValueError(f"board cell: 'align' must be one of {ALIGNS}")
            lines.append(f"align = {_toml_string(align)}")
        valign = cell.get("valign", "top")
        if valign != "top":
            if valign not in VALIGNS:
                raise ValueError(f"board cell: 'valign' must be one of {VALIGNS}")
            lines.append(f"valign = {_toml_string(valign)}")
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", text=True)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def save_board_source(
    name: str,
    text: str,
    boards_dir: Path,
    widgets_dir: Path,
    custom_widgets_dir: Path | None = None,
    custom_boards_dir: Path | None = None,
) -> str:
    root, source = _find_board(name, boards_dir, custom_boards_dir)
    if source == BUNDLED_SOURCE:
        # Editing a bundled board writes a local override instead of touching the repo.
        root = _write_board_root(boards_dir, custom_boards_dir)
    path = root / name / BOARD_MANIFEST
    spec = parse_board_source(text, name, widgets_dir, custom_widgets_dir)
    _write_atomic(path, text)
    return spec.name


def list_boards(boards_dir: Path, custom_boards_dir: Path | None = None) -> list[str]:
    names: set[str] = set()
    for root, _ in _board_roots(boards_dir, custom_boards_dir):
        if root.is_dir():
            names.update(
                path.name
                for path in root.iterdir()
                if (path / BOARD_MANIFEST).is_file()
            )
    return sorted(names)


def summarize_board(
    name: str,
    boards_dir: Path,
    widgets_dir: Path,
    custom_widgets_dir: Path | None = None,
    custom_boards_dir: Path | None = None,
) -> dict:
    try:
        root, source = _find_board(name, boards_dir, custom_boards_dir)
    except FileNotFoundError:
        root, source = boards_dir, None
    path = root / name / BOARD_MANIFEST
    summary: dict = {
        "name": name,
        "title": name,
        "source": source,
        "frame": False,
        "mode": None,
        "widget_count": 0,
        "valid": False,
        "error": None,
        "updated": path.stat().st_mtime if path.is_file() else None,
    }
    try:
        spec = load_board(
            name, boards_dir, widgets_dir, custom_widgets_dir, custom_boards_dir
        )
    except (OSError, TypeError, ValueError) as e:
        summary["error"] = str(e)
        return summary
    summary.update(
        {
            "title": spec.name,
            "frame": spec.frame,
            "mode": "auto" if spec.regions is None else "cells",
            "widget_count": len(spec.widgets),
            "valid": True,
        }
    )
    return summary


def list_board_summaries(
    boards_dir: Path,
    widgets_dir: Path,
    custom_widgets_dir: Path | None = None,
    custom_boards_dir: Path | None = None,
) -> list[dict]:
    return [
        summarize_board(
            name,
            boards_dir,
            widgets_dir,
            custom_widgets_dir,
            custom_boards_dir,
        )
        for name in list_boards(boards_dir, custom_boards_dir)
    ]


def read_board_source(
    name: str, boards_dir: Path, custom_boards_dir: Path | None = None
) -> str:
    root, _ = _find_board(name, boards_dir, custom_boards_dir)
    return (root / name / BOARD_MANIFEST).read_text(encoding="utf-8")


def _template_cells(
    names: Sequence[str], template: str
) -> tuple[list[dict] | None, list[str]]:
    if template == "auto":
        return None, list(names)
    if template == "single":
        return None, list(names[:1])
    if template == "columns":
        width = 1.0 / len(names)
        return [
            {
                "widget": name,
                "x": index * width,
                "y": 0.0,
                "width": width,
                "height": 1.0,
            }
            for index, name in enumerate(names)
        ], []
    if template == "grid":
        columns = max(1, math.ceil(math.sqrt(len(names))))
        rows = max(1, math.ceil(len(names) / columns))
        width, height = 1.0 / columns, 1.0 / rows
        return [
            {
                "widget": name,
                "x": (index % columns) * width,
                "y": (index // columns) * height,
                "width": width,
                "height": height,
            }
            for index, name in enumerate(names)
        ], []
    raise ValueError(f"unknown board template: {template!r}")


def create_board(
    name: str,
    boards_dir: Path,
    widgets_dir: Path | None = None,
    *,
    template: str = "auto",
    widget_names: Sequence[str] | None = None,
    frame: bool = False,
    custom_widgets_dir: Path | None = None,
    custom_boards_dir: Path | None = None,
) -> None:
    safe_name(name)
    if template not in TEMPLATES:
        raise ValueError(f"unknown board template: {template!r}")
    if _board_exists(name, boards_dir, custom_boards_dir):
        raise FileExistsError(f"board already exists: {name}")
    path = _write_board_root(boards_dir, custom_boards_dir) / name
    if path.exists():
        raise FileExistsError(f"board already exists: {name}")

    available: list[str] = []
    if widgets_dir is not None:
        widgets, _ = scan_widgets(widgets_dir, custom_widgets_dir)
        available = [widget.id for widget in widgets]

    names = list(widget_names or [])
    if names:
        for widget_name in names:
            safe_name(widget_name)
            if widgets_dir is not None:
                resolve_widget(widget_name, widgets_dir, custom_widgets_dir)
    elif widgets_dir is not None:
        names = available[:4]
    if not names:
        raise ValueError("no widgets available; add a widget directory first")
    if template == "single":
        names = names[:1]
    if not names:
        raise ValueError("no widgets selected")

    cells, widgets = _template_cells(names, template)
    model = {
        "name": name,
        "frame": frame,
        "mode": "auto" if cells is None else "cells",
        "widgets": widgets,
        "cells": cells or [],
    }
    source = source_from_model(model)
    _write_atomic(path / BOARD_MANIFEST, source)


def delete_board(
    name: str, boards_dir: Path, custom_boards_dir: Path | None = None
) -> None:
    root, source = _find_board(name, boards_dir, custom_boards_dir)
    if source == BUNDLED_SOURCE and _is_bundled_root(boards_dir):
        raise ValueError(
            "bundled boards cannot be deleted; duplicate the board into "
            "custom-boards first"
        )
    shutil.rmtree(root / name)


def rename_board(
    name: str,
    new_name: str,
    boards_dir: Path,
    custom_boards_dir: Path | None = None,
) -> None:
    safe_name(new_name)
    root, source = _find_board(name, boards_dir, custom_boards_dir)
    if source == BUNDLED_SOURCE and _is_bundled_root(boards_dir):
        raise ValueError(
            "bundled boards cannot be renamed; duplicate the board into "
            "custom-boards first"
        )
    target = root / new_name
    if _board_exists(new_name, boards_dir, custom_boards_dir) or target.exists():
        raise FileExistsError(f"board already exists: {new_name}")
    (root / name).rename(target)


def duplicate_board(
    name: str,
    new_name: str,
    boards_dir: Path,
    widgets_dir: Path,
    custom_widgets_dir: Path | None = None,
    custom_boards_dir: Path | None = None,
) -> None:
    safe_name(new_name)
    spec = load_board(
        name, boards_dir, widgets_dir, custom_widgets_dir, custom_boards_dir
    )
    target = _write_board_root(boards_dir, custom_boards_dir) / new_name
    if _board_exists(new_name, boards_dir, custom_boards_dir) or target.exists():
        raise FileExistsError(f"board already exists: {new_name}")
    model = board_to_model(spec, new_name)
    model["name"] = new_name
    _write_atomic(target / BOARD_MANIFEST, source_from_model(model))


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

    def errors(self) -> list[dict]:
        return [
            {"widget": cell.widget.id, "message": cell.error}
            for cell in self.cells
            if cell.error
        ]

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
