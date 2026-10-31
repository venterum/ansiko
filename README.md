<p align="center"><img src="ansiko.svg" width="72" height="72" alt="Ansiko logo"></p>

# Ansiko

**Turn an old Android phone into a glass terminal for your Linux machine.**

The phone runs a tiny app that does one thing: it shows what your computer sends it.
No keyboard, no logic, no state. Type on your computer, watch it appear on the phone, or
build a wall of ASCII widgets and push it to the screen with one click.

> Status: daemon, PTY/terminal mode, Android client, board mode, visual board editor,
> live ANSI preview, widget catalog and QR pairing work.

<!-- Put a photo or short video here: phone on a stand, asciiquarium + a currency widget. -->

## Two modes

**Terminal mode.** Run any console program and mirror it to the phone until you exit:

```sh
ansiko run asciiquarium
ansiko run fastfetch
ansiko run tty-clock -c
```

**Board mode.** A grid of widgets, defined by a board file and pushed to the device:

- exchange rates from any API
- countdown to anything
- system stats, weather, build status, whatever a script can print

Boards can pack widgets automatically or place them in explicit fractional cells with
server-drawn frames. The web editor can drag, resize, preview and push a board without
touching TOML; the raw source is still one click away.

The phone doesn't know the difference: in both cases it receives a stream of ANSI bytes
and draws them.

## How it works

```
 Web editor / CLI (on your computer)
            │  HTTP / WebSocket
            ▼
   ansiko daemon (Linux): PTY, layouts, widget scheduler
            │  WebSocket: raw ANSI bytes
            ▼
   Android app: read-only terminal view, screen always on
```

The PTY is always created at the phone's exact grid size (columns x rows), which the
phone reports when it connects. This is the only thing the phone ever tells the server.

## Install

Requires Python 3.11+ on a Linux machine.

```sh
uv tool install ./server    # or: pipx install ./server
cp ansiko.example.toml ansiko.local.toml
# edit the token and, for the phone, the LAN address
ansiko serve --host <lan-ip>
```

`ansiko.local.toml` is ignored by git. Keep the server on your local network (or behind
Tailscale/WireGuard).

Then install the Android app from [Releases](../../releases), or build it from `android/`:

```sh
cd android
./gradlew assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Enter the same host, port, and token. Long-press the terminal to change them.

## Web UI and pairing

Open `http://<lan-ip>:8765/` on the computer and enter the token. The dashboard shows
the phone state and a board library. The visual editor has:

- a palette of existing widgets;
- drag-and-drop and eight resize handles in free layout;
- snap to a 5% grid, collision checks, undo/redo and keyboard nudge;
- automatic packing, equal columns, grid and vertical-stack presets;
- a live ANSI monitor with a full-screen mode;
- a raw TOML tab with line/column validation;
- save, save & push, duplicate, rename and delete.

The **Widgets** page lists every manifest, shows its size/interval/timeout, runs a
single test and can start a board with that widget. Widget scripts are not edited in the
browser; they are normal files in `widgets/` (bundled examples) or `custom-widgets/`
(your own, ignored by git). A custom widget with the same id overrides the bundled one.
The dashboard is intentionally Graphite-only and uses self-hosted Archivo + IBM Plex Mono.
The interface supports English and Russian; it auto-detects the browser language and the
RU/EN switch is available on the login screen and in the sidebar.

The same page shows a pairing QR code. In the app, long-press the terminal, then tap
**Scan pairing QR**. The QR contains the host, port, and token, so the app fills all three
fields. The QR is only shown after logging in; keep this page on your LAN.

## Widgets

A widget is a script that prints text, plus a small manifest. Any language works.

```
widgets/clock/
├── widget.toml
└── run.py
```

```toml
# widget.toml
name        = "clock"
description = "Local time"
command     = "./run.py"
interval    = 1      # seconds between runs
width       = 20
height      = 5
timeout     = 5
```

```python
#!/usr/bin/env python3
import time
print(time.strftime("%H:%M:%S"))
```

The widget receives its size in `ANSIKO_COLS` and `ANSIKO_ROWS`. If a script fails, only
its own cell shows an error; the rest of the board keeps running. A ten-line script is
usually enough.

A board can list widget directories and let the server pack them:

```toml
# boards/desk/board.toml
name = "desk"
widgets = ["clock", "calendar"]
```

Or place cells explicitly. Coordinates and sizes are fractions of the phone screen, so
the board survives rotation:

```toml
name = "desk"
frame = true

[[cells]]
widget = "clock"
x = 0.0
y = 0.0
width = 0.5
height = 1.0

[[cells]]
widget = "calendar"
x = 0.5
y = 0.0
width = 0.5
height = 1.0
```

`frame = true` asks the server to draw a titled box around every cell. The widget gets
the inner `ANSIKO_COLS` and `ANSIKO_ROWS`, so it does not need to draw its own border.

This checkout bundles four small widgets: `clock`, `calendar`, `sysinfo` and `banner`.
They are ordinary directories with a manifest and an executable; copy one as a starting
point. Put personal widgets in `custom-widgets/`; that directory is ignored by git and
merged with the bundled catalog. The dashboard also has a **Widgets** catalog and a
**[widget guide](docs/widgets.md)**.

Tip: `figlet`, `toilet`, `rich`, and `plotext` are great for big digits, boxes, and charts.

## Documentation

- [Widget guide](docs/widgets.md) — manifest, environment, ANSI, errors, testing.
- [Board format](docs/boards.md) — auto/free layouts, frames, visual editor.
- [Web dashboard](docs/web-ui.md) — library, editor, monitor, widgets, pairing, shortcuts.
- [Protocol](docs/protocol.md) — phone, terminal and preview WebSockets; HTTP API.

## CLI

```
ansiko serve              start the daemon
ansiko run <command...>   run a program on the phone until exit / Ctrl+C
ansiko push <board>       switch the phone to a saved board
ansiko status             show the connected device and current mode
```

## Security

The daemon is effectively a remote shell. A token is required, and by default it should
only listen on your local network. Do not expose it to the internet. Put the token in
`ansiko.local.toml` (ignored by git) rather than in tracked files. The web UI login and
pairing QR both use that token, so use a long random one, not a short PIN.

## Roadmap

- [x] Daemon: WebSocket + PTY, live `bash` on the phone
- [x] Android client: read-only terminal view, auto-reconnect, keep screen on
- [x] Terminal mode CLI (`ansiko run`)
- [x] Board mode: auto packing, explicit fractional cells, frames, scheduler
- [x] Web UI: token login, board list/editor, push, QR pairing
- [x] Visual board editor: drag/resize, snapping, presets, undo/redo, live preview
- [x] Widget catalog, examples and documentation
- [ ] Extras: page rotation, burn-in protection, tap zones

## Contributing

Widgets are the easiest way to contribute: add a directory under `widgets/` with a
manifest and a script. Keep them small and dependency-free where possible. Read the
[widget guide](docs/widgets.md) first, and test the script with `ANSIKO_COLS` and
`ANSIKO_ROWS` set.

## License

GPL 3 or higher
