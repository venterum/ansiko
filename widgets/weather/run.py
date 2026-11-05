#!/usr/bin/env python3
"""Static St. Petersburg weather card; no API."""

import os
import re

ANSI = re.compile(r"\x1b\[[0-9;]*m")
LINES = [
    "\x1b[1;36mСАНКТ-ПЕТЕРБУРГ\x1b[0m",
    "",
    "\x1b[1;33m+7°C\x1b[0m  пасмурно",
    "\x1b[2mдождь · ветер 4 м/с\x1b[0m",
]


def width(text: str) -> int:
    return len(ANSI.sub("", text))


def main() -> int:
    try:
        cols = int(os.environ["ANSIKO_COLS"])
        rows = int(os.environ["ANSIKO_ROWS"])
    except (KeyError, ValueError):
        return 2

    top = max((rows - len(LINES)) // 2, 0)
    for _ in range(top):
        print()
    for line in LINES:
        print(" " * max((cols - width(line)) // 2, 0) + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
