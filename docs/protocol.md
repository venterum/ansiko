# Protocol

All endpoints are served by the same daemon. HTTP APIs require the `ansiko_token`
cookie set by `/api/login`, or an `Authorization: Bearer <token>` header. The
phone uses a token in its first WebSocket message instead.

## Phone display: `/ws/display`

Phone to daemon, text frames:

```json
{"type": "hello", "token": "...", "cols": 40, "rows": 30}
{"type": "resize", "cols": 50, "rows": 35}
```

Daemon to phone:

- binary frames: raw bytes for the terminal emulator;
- text frames: `{"type": "reset"}` clears the emulator.

The phone never sends keystrokes or widget requests. It only reports its grid
size. The daemon creates PTYs and board cells at that size.

## Terminal client: `/ws/session`

Authenticated HTTP upgrade. Client to daemon:

```json
{"type": "start", "argv": ["fastfetch"], "cwd": null}
```

After the start message, client-to-daemon binary frames are keystrokes.
Daemon-to-client binary frames are program output. Text frames are control
messages: `size`, `exit`, `error`.

Only one session or board is active at a time.

## Board preview: `/ws/preview`

Authenticated HTTP upgrade, used only by the web dashboard. Client to daemon:

```json
{"type": "preview", "source": "name = \"demo\"\nwidgets = [\"clock\"]\n", "cols": 40, "rows": 30}
```

Daemon to browser:

- binary frames: the same composed ANSI frames a phone would receive;
- text frames: `{"type": "preview_ready"}` or
  `{"type": "preview_error", "error": "...", "line": 2, "column": 3}`.

Sending a new `preview` message replaces the temporary board. Closing the socket
stops it. Preview never touches the active board, the phone socket or a PTY.

## HTTP API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/login` | Set the auth cookie. |
| `POST` | `/api/logout` | Clear the auth cookie. |
| `GET` | `/api/session` | Public boolean: is this browser authenticated? |
| `GET` | `/api/status` | Version, display, session and active board/errors. |
| `GET` | `/api/boards` | Board names. Add `?details=1` for summaries. |
| `POST` | `/api/boards` | Create from `{name, template, widgets, frame}`. |
| `POST` | `/api/boards/validate` | Parse source and return a layout model. |
| `GET` | `/api/boards/{name}` | Read `board.toml` as text. |
| `PUT` | `/api/boards/{name}` | Validate and atomically save source. |
| `DELETE` | `/api/boards/{name}` | Delete a board folder. |
| `POST` | `/api/boards/{name}/duplicate` | Copy to `{name}`. |
| `POST` | `/api/boards/{name}/rename` | Rename folder to `{name}`. |
| `POST` | `/api/push` | Activate a board on the phone. |
| `POST` | `/api/stop` | Stop the board/session and show idle. |
| `GET` | `/api/widgets` | Widget manifests and manifest errors. |
| `POST` | `/api/widgets/run` | Run one widget once for the catalog test button. |
| `GET` | `/api/pair` | Pairing URL. |
| `GET` | `/api/pair.svg` | Pairing QR as SVG. |

Board source is capped at 64 KiB. Display dimensions are capped at 500 columns
and 500 rows.

## Frame composition

Each board render starts with `ESC[2J ESC[H ESC[?25l`, then draws cells with
cursor addressing. A framed cell draws a `┌ title ─┐` border in cyan. Widget
output is clipped to the content area, preserving ANSI sequences. Every line is
followed by `ESC[0m`, so a widget cannot leak a color into its neighbour.
