# Web dashboard

The daemon serves a small dashboard at `http://<host>:<port>/`. It is a client
of the daemon API, not a separate service. There is no build step and no CDN:
the page works on a local network without internet access. The UI is
Graphite-only, with self-hosted Archivo and IBM Plex Mono. The UI supports
English and Russian, auto-detects the browser language and remembers the
RU/EN choice in localStorage.

## Login

Use the token from `ansiko.local.toml`. The dashboard stores it in an HttpOnly,
SameSite=Strict cookie. Wrong tokens are rejected by the daemon. Locking the
dashboard clears the cookie.

If you run the daemon with `--host 127.0.0.1`, open the page on the same machine.
For the phone, bind to the LAN address:

```sh
ansiko serve --host 192.168.1.50
```

## Boards

The library shows title, folder, source (`CUSTOM` or `BUNDLED`), layout mode,
widget count and validation state. Custom boards live in `custom-boards/` and
override bundled boards with the same folder name. Actions:

- **New board** — choose a folder name, a starting template and widgets. The
  folder is created under `custom-boards/`.
- **Open** — layout and source editor.
- **Duplicate** — copies `board.toml` into `custom-boards/`; widget directories
  are shared.
- **Delete** — removes the board folder after confirmation. It does not delete
  widgets. If the board is on the phone, the display returns to idle.

The **Ready / Issues** filter helps find boards with a missing widget or invalid
TOML. Invalid boards can still be opened in Source mode and fixed.

## Layout editor

See [boards.md](boards.md) for the file format and a tour of auto/free layouts,
snap, collision checks, undo/redo, quick layouts and the inspector.

The **Monitor** uses `/ws/preview`, an authenticated WebSocket that runs a
temporary `Board` and streams real ANSI frames. **Preview**, the expand icon or
`P` opens it full-screen; `Esc` closes it. It never reads or controls the phone
socket, and it does not change the active board.

## Widgets

The catalog merges `custom-widgets/` (first) and `widgets/` (bundled), with a
`CUSTOM` or `BUNDLED` tag. Custom entries override bundled ones with the same id.
It shows the default size, interval, timeout and optional description. **Test**
runs the script once at the current display size; **Use in board** opens the new
board dialog with that widget selected.

Manifest errors are listed separately and do not break the rest of the catalog.
See [widgets.md](widgets.md).

## Pairing

**Pair phone** shows a QR code containing host, port and token. In the Android
app, long-press the terminal, tap **Scan pairing QR**, and save. Open the
dashboard through the computer's LAN address, not `localhost`, otherwise the QR
points the phone at itself.

The QR is only shown after login. It contains the daemon token, so do not share
the screen or the pairing URL.

## Status and controls

The top bar shows phone connection and active mode. The sidebar shows the same
summary and a **Stop display** button, which stops the active board or terminal
session and sends the idle screen. Widget errors are reported by `/api/status`
and shown in the dashboard.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl`/`Cmd` + `S` | Save the open board |
| `Ctrl`/`Cmd` + `Z` | Undo |
| `Ctrl`/`Cmd` + `Shift` + `Z` | Redo |
| `Delete` | Delete selected cell |
| `Esc` | Deselect / close dialog / close full preview |
| `P` | Open full-screen monitor |

## Security

The dashboard is a remote control for a shell-adjacent daemon. Use a long random
token, keep the daemon on a trusted network, and do not expose port 8765 to the
public internet. The web UI cannot prevent a malicious widget from doing
whatever the daemon user can do; review widget code.
