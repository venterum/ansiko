#!/usr/bin/env python3
"""Capture one tty-clock frame through tmux.

tty-clock is an ncurses program, so it needs a real terminal; tmux gives it one
and capture-pane returns the visible screen as ANSI text.
"""

import os
import shlex
import shutil
import subprocess
import sys
import time


def main() -> int:
    try:
        cols = int(os.environ["ANSIKO_COLS"])
        rows = int(os.environ["ANSIKO_ROWS"])
    except (KeyError, ValueError):
        print("ANSIKO_COLS/ANSIKO_ROWS missing", file=sys.stderr)
        return 2

    tmux = shutil.which("tmux")
    clock = shutil.which("tty-clock")
    if not tmux or not clock:
        print("this widget needs tty-clock and tmux", file=sys.stderr)
        return 1

    socket = "ansiko-clock"
    name = f"ansiko-{os.getpid()}-{time.time_ns()}"
    command = f"{shlex.quote(clock)} -c -s -D -C 6"
    tmux_cmd = [tmux, "-L", socket, "-f", "/dev/null"]

    try:
        subprocess.run(
            tmux_cmd
            + [
                "new-session",
                "-d",
                "-s",
                name,
                "-x",
                str(max(cols, 2)),
                "-y",
                str(max(rows, 2)),
                command,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.25)
        captured = subprocess.run(
            tmux_cmd + ["capture-pane", "-p", "-e", "-t", name],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        sys.stdout.buffer.write(captured.stdout)
        return 0
    except (OSError, subprocess.CalledProcessError) as e:
        print(f"tty-clock widget: {e}", file=sys.stderr)
        return 1
    finally:
        subprocess.run(
            tmux_cmd + ["kill-session", "-t", name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    raise SystemExit(main())
