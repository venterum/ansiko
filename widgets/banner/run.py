#!/usr/bin/env python3
"""A small ANSI banner; useful as a board header."""

from __future__ import annotations

import os

BANNER = r"""
  _   _  _  ___ _____ _  __
 /_\ | \| |/ __|_   _| |/ /
/ _ \| .` |\__ \ | | | ' <
/_/ \_\_|\_|___/ |_| |_|\_\
"""


def main() -> None:
    cols = max(1, int(os.environ.get("ANSIKO_COLS", "30")))
    rows = max(1, int(os.environ.get("ANSIKO_ROWS", "6")))
    lines = [line[:cols] for line in BANNER.strip("\n").splitlines()]
    if rows >= len(lines) + 1:
        lines.append("glass terminal".center(cols))
    print("\x1b[1;36m" + "\n".join(lines[:rows]) + "\x1b[0m")


if __name__ == "__main__":
    main()
