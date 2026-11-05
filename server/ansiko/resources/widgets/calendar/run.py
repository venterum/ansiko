#!/usr/bin/env python3
"""This month's calendar, with today highlighted."""

from __future__ import annotations

import calendar
import os
from datetime import date


def main() -> None:
    cols = max(1, int(os.environ.get("ANSIKO_COLS", "24")))
    rows = max(1, int(os.environ.get("ANSIKO_ROWS", "9")))
    today = date.today()
    title = f"{calendar.month_name[today.month]} {today.year}"
    lines = [title.center(cols)]
    if cols >= 20:
        lines.append("Mo Tu We Th Fr Sa Su"[:cols])
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(
            today.year, today.month
        )
        for week in weeks:
            cells = []
            for day in week:
                if day == 0:
                    cells.append("  ")
                elif day == today.day:
                    cells.append(f"\x1b[7m{day:2d}\x1b[0m")
                else:
                    cells.append(f"{day:2d}")
            lines.append(" ".join(cells)[:cols])
    else:
        lines.append(f"today: {today.isoformat()}")
    print("\n".join(lines[:rows]))


if __name__ == "__main__":
    main()
