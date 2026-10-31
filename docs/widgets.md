# Widgets

A widget is a small program that prints text. Ansiko runs it on an interval,
places its output inside a board cell, and never gives it control of the phone.
Any language works: Python, shell, Node, Go, or a compiled binary. Put
personal widgets in `custom-widgets/` so they stay out of git; bundled examples
live in `widgets/`. Custom widgets with the same directory name override bundled
ones.

```
widgets/clock/
├── widget.toml
└── run.py
```

## `widget.toml`

```toml
name        = "clock"
description = "Local time and date"
command     = "./run.py"
interval    = 1
width       = 24
height      = 6
timeout     = 2
```

| Key | Required | Meaning |
| --- | --- | --- |
| `name` | no | Display name. Defaults to the directory name. |
| `description` | no | Short sentence shown in the web catalog. |
| `command` | yes | Command line, split like a shell would split it. |
| `interval` | no | Seconds between runs. Default `1`, minimum `0.1`. |
| `width` | no | Suggested width in terminal cells. Default `20`. |
| `height` | no | Suggested height in terminal cells. Default `5`. |
| `timeout` | no | Kill the script after this many seconds. Default `5`, minimum `0.1`. |

`command` can be a local executable (`./run.py`, `run.sh`) or a program on
`PATH` (`fastfetch`, `figlet -f big`). A relative path is resolved from the
widget directory. The script does **not** need to be shell syntax; it is
executed directly. If the command starts with a shell builtin, wrap it:

```toml
command = "/bin/sh -c 'printf hello'"
```

## What the script receives

| Value | Meaning |
| --- | --- |
| `ANSIKO_COLS` | Content width in terminal cells after borders are removed. |
| `ANSIKO_ROWS` | Content height in terminal cells after borders are removed. |
| working directory | The widget directory. |
| `TERM` | Inherited from the daemon environment; do not depend on it. |

Print UTF-8 to stdout and exit with status `0`. The server strips trailing
newlines. ANSI SGR colors, cursor addressing, clearing and most common control
sequences pass through to the phone and to the web preview.

A non-zero exit, timeout, missing executable or invalid manifest shows an error
inside that widget's cell. Other widgets keep running.

## Minimal examples

### Python

```python
#!/usr/bin/env python3
import os
from datetime import datetime

cols = int(os.environ.get("ANSIKO_COLS", "20"))
print(datetime.now().strftime("%H:%M:%S").center(cols))
```

### Shell

```sh
#!/bin/sh
printf '\033[36m%s\033[0m\n' "$(date +%H:%M)"
```

### One-shot API call

```sh
#!/bin/sh
# Do not put an API key in a tracked file.
curl -fsS --max-time 3 "https://api.example.com/value?key=$MY_API_KEY"
```

Network failures should be handled by the script, or the cell will briefly show
an error until the next run.

## Layout rules

- Prefer ASCII and box-drawing characters. They keep the cell's column grid
  stable in every terminal font.
- Wide glyphs (emoji, CJK) occupy two columns. The server clips them carefully,
  but a widget should avoid mixing them with box drawing.
- The daemon starts a new process for each run. Keep state in a file only if you
  really need it; a widget that takes longer than `interval` drifts.
- `width` and `height` are suggestions for automatic layouts. Explicit board
  cells can be larger or smaller; the widget receives the real inner size.
- If a widget writes a frame itself, set the board/cell frame off to avoid a
  double border.

## Custom directory

The daemon reads `custom-widgets/` first and `widgets/` second:

```text
custom-widgets/weather/   -> id "weather", source "custom"
widgets/clock/            -> id "clock", source "bundled"
custom-widgets/clock/     -> overrides the bundled clock
```

Use another location with:

```toml
# ansiko.local.toml
custom_widgets = "my-widgets"
```

or `ansiko serve --custom-widgets my-widgets`. The web catalog shows a
`CUSTOM` or `BUNDLED` tag for every entry. The board file still references
the directory id, so no board migration is needed.

## Test a widget

From its directory:

```sh
ANSIKO_COLS=30 ANSIKO_ROWS=8 ./run.py
```

Or use **Widgets → Test** in the web dashboard. The test runs with the current
phone grid size when it is known. The daemon logs nothing by default; errors are
shown in the dashboard and in the widget cell.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `cannot start: No such file or directory` | `command` path, executable bit (`chmod +x`), shebang. |
| `exit 1: ...` | Run the command manually in the widget directory. |
| `timeout after 2s` | Raise `timeout` or make the script faster. |
| `missing widget.toml` | The directory is not a widget, or the file name is misspelled. |
| Cell is empty | The script exited 0 but wrote nothing, or output was only whitespace. |
| Cell shows an error after a while | The process hit the timeout; check the error text. |

## Security

Widgets are trusted local code. They run with the daemon user's permissions, so
treat a widget directory like a shell script: review it before running. The web
catalog only reads manifests; it does not execute a widget until you press
**Test** or push a board that uses it. Keep the daemon on a trusted network and
never commit tokens or personal data to a widget directory.
