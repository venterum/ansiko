# Ansiko

**Turn an old Android phone into a glass terminal for your Linux machine.**

The phone runs a tiny app that does one thing: it shows what your computer sends it.
No keyboard, no logic, no state. Type on your computer, watch it appear on the phone, or
build a wall of ASCII widgets and push it to the screen with one click.

> Status: the daemon, PTY/terminal mode, Android client, and a minimal board mode
> work. The web editor is the next milestone.

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

The first version packs widgets in a row automatically. The web editor comes later.

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

Then install the Android app from [Releases](../../releases), or build it from `android/`,
and enter the same host, port, and token. Long-press the terminal to change them.

## Widgets

A widget is a script that prints text, plus a small manifest. Any language works.

```
widgets/clock/
├── widget.toml
└── run.py
```

```toml
# widget.toml
name     = "clock"
command  = "./run.py"
interval = 1      # seconds between runs
width    = 20
height   = 5
timeout  = 5
```

```python
#!/usr/bin/env python3
import time
print(time.strftime("%H:%M:%S"))
```

The widget receives its size in `ANSIKO_COLS` and `ANSIKO_ROWS`. If a script fails, only
its own cell shows an error; the rest of the board keeps running. This makes widgets easy
to write by hand or to generate with an AI assistant: "write a widget that shows X" is a
ten-line script.

A board lists widget directories:

```toml
# boards/default/board.toml
name = "default"
widgets = ["clock", "date"]
```

`clock` and `date` are bundled examples under `widgets/`.

Tip: `figlet`, `toilet`, `rich`, and `plotext` are great for big digits, boxes, and charts.

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
`ansiko.local.toml` (ignored by git) rather than in tracked files.

## Roadmap

- [x] Daemon: WebSocket + PTY, live `bash` on the phone
- [x] Android client: read-only terminal view, auto-reconnect, keep screen on
- [x] Terminal mode CLI (`ansiko run`)
- [x] Board mode: automatic grid packing, script widgets, scheduler
- [ ] Web editor: layout preview, widget code, send to device
- [ ] Extras: page rotation, burn-in protection, tap zones

## Contributing

Widgets are the easiest way to contribute: add a directory under `widgets/` with a
manifest and a script. Keep them small and dependency-free where possible.

## License

GPL 3 or higher
