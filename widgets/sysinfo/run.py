#!/usr/bin/env python3
"""A small local system snapshot."""

from __future__ import annotations

import os
import platform
import shutil
import socket
from pathlib import Path


def read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def uptime() -> str:
    raw = read("/proc/uptime").split()
    if not raw:
        return "?"
    seconds = int(float(raw[0]))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    if days:
        return f"{days}d {hours:02d}h {minutes:02d}m"
    return f"{hours:02d}h {minutes:02d}m"


def memory() -> str:
    values: dict[str, int] = {}
    for line in read("/proc/meminfo").splitlines():
        key, _, rest = line.partition(":")
        chunks = rest.split()
        if chunks:
            values[key] = int(chunks[0])
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    if not total:
        return "?"
    used = total - available
    return f"{used / 1024 / 1024:.1f}/{total / 1024 / 1024:.1f} GiB"


def main() -> None:
    cols = max(1, int(os.environ.get("ANSIKO_COLS", "38")))
    rows = max(1, int(os.environ.get("ANSIKO_ROWS", "8")))
    load = read("/proc/loadavg").split()[:3]
    disk = shutil.disk_usage("/")
    lines = [
        f"\x1b[36mhost\x1b[0m  {socket.gethostname()}",
        f"\x1b[36mkern\x1b[0m  {platform.release()}",
        f"\x1b[36mup\x1b[0m    {uptime()}",
        f"\x1b[36mload\x1b[0m  {' '.join(load) if load else '?'}",
        f"\x1b[36mmem\x1b[0m   {memory()}",
        f"\x1b[36mdisk\x1b[0m  {disk.used / disk.total * 100:.0f}% of {disk.total / 1024**3:.0f} GiB",
    ]
    print("\n".join(line[: max(cols * 2, cols)] for line in lines[:rows]))


if __name__ == "__main__":
    main()
