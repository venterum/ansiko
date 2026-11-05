#!/usr/bin/env python3
"""A large HH:MM clock with a date line."""

from __future__ import annotations

import os
from datetime import datetime

# Five rows per digit. ASCII only, so it survives every monospace font.
FONT = {
    "0": ["###", "# #", "# #", "# #", "###"],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["###", "  #", "###", "#  ", "###"],
    "3": ["###", "  #", "###", "  #", "###"],
    "4": ["# #", "# #", "###", "  #", "  #"],
    "5": ["###", "#  ", "###", "  #", "###"],
    "6": ["###", "#  ", "###", "# #", "###"],
    "7": ["###", "  #", "  #", "  #", "  #"],
    "8": ["###", "# #", "###", "# #", "###"],
    "9": ["###", "# #", "###", "  #", "###"],
    ":": ["   ", " # ", "   ", " # ", "   "],
}


def width() -> int:
    return max(1, int(os.environ.get("ANSIKO_COLS", "24")))


def height() -> int:
    return max(1, int(os.environ.get("ANSIKO_ROWS", "6")))


def center(line: str, cols: int) -> str:
    return line[:cols].center(cols)


def main() -> None:
    cols, rows = width(), height()
    now = datetime.now()
    stamp = now.strftime("%H:%M")
    lines: list[str] = []
    if cols >= len(stamp) * 4 - 1 and rows >= 6:
        big = ["" for _ in range(5)]
        for char in stamp:
            glyph = FONT.get(char, FONT[":"])
            for index in range(5):
                if big[index]:
                    big[index] += " "
                big[index] += glyph[index]
        lines.extend(center(line, cols) for line in big)
        lines.append(center(now.strftime("%A, %d %B"), cols))
    else:
        lines.append(center(now.strftime("%H:%M:%S"), cols))
        if rows >= 3:
            lines.append(center(now.strftime("%a %d %b"), cols))
    output = "\n".join(lines[:rows])
    print(f"\x1b[1;36m{output}\x1b[0m")


if __name__ == "__main__":
    main()
