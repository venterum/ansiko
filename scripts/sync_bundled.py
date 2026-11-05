#!/usr/bin/env python3
"""Mirror the repository's bundled boards/widgets into the Python package.

The top-level directories are the editable examples. The package copy makes
``uv tool install ./server`` work from any working directory, because wheels
cannot reference files outside the package. Run this after changing either
directory; ``tests/test_resources.py`` fails when the copies drift.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "server" / "ansiko" / "resources"


def main() -> None:
    for name in ("boards", "widgets"):
        source = ROOT / name
        destination = TARGET / name
        if not source.is_dir():
            raise SystemExit(f"missing bundled directory: {source}")
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(
            source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
        )
        print(f"synced {source} -> {destination}")


if __name__ == "__main__":
    main()
