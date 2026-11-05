#!/usr/bin/env python3
"""Now playing: title, artist and progress, read from MPRIS via playerctl."""

from __future__ import annotations

import os
import shutil
import subprocess
import time

FORMAT = "{{status}}\x1f{{artist}}\x1f{{title}}\x1f{{position}}\x1f{{mpris:length}}"

SCROLL_SPEED = 2  # characters per second
SCROLL_GAP = "     "  # shown between the end of the title and its next repeat


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def fmt_time(microseconds: int) -> str:
    seconds = max(microseconds, 0) // 1_000_000
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return (
        f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"
    )


def to_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


def parse(output: str) -> list[str] | None:
    rows = [line.split("\x1f") for line in output.splitlines()]
    rows = [row for row in rows if len(row) == 5]
    if not rows:
        return None
    return next((row for row in rows if row[0] == "Playing"), rows[0])


def marquee(text: str, width: int, now: float) -> str:
    """Fit text into width; if it is too long, scroll it as a loop driven by the clock.

    The widget is a fresh process on every refresh, so the offset comes from the time
    rather than from saved state. Every instance agrees on the same frame.
    """
    if len(text) <= width:
        return text
    loop = text + SCROLL_GAP
    offset = int(now * SCROLL_SPEED) % len(loop)
    return (loop + loop)[offset : offset + width]


def progress_line(position: int, length: int, cols: int) -> str:
    times = (
        fmt_time(position)
        if length <= 0
        else f"{fmt_time(position)}/{fmt_time(length)}"
    )
    room = cols - len(times) - 1
    if length <= 0 or room < 9:
        return times
    cells = room - 2  # brackets
    filled = round(cells * min(position, length) / length)
    return "[" + "#" * filled + "-" * (cells - filled) + "] " + times


def main() -> int:
    cols = env_int("ANSIKO_COLS", 30)
    rows = env_int("ANSIKO_ROWS", 6)
    if not shutil.which("playerctl"):
        print("playerctl не установлен")
        return 1

    try:
        result = subprocess.run(
            ["playerctl", "metadata", "--format", FORMAT],
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        result = None

    track = parse(result.stdout) if result else None
    if track is None:
        print("ничего не играет".center(cols))
        return 0

    status, artist, title, position, length = track
    marker = "|| " if status == "Paused" else "> " if status == "Playing" else ""
    # shortcut: one-column glyphs assumed, an emoji in a title may overflow the cell.
    # The marker stays put; only the title scrolls.
    title_line = marker + marquee(
        title or artist or "?", cols - len(marker), time.time()
    )
    lines = [("\x1b[1;36m", title_line)]
    if rows >= 3 and artist:
        lines.append(("\x1b[2m", artist[:cols]))
    if rows >= 4:
        lines.append(
            ("\x1b[32m", progress_line(to_int(position), to_int(length), cols))
        )

    for color, line in lines[:rows]:
        print(f"{color}{line}\x1b[0m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
