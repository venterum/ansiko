"""The ansiko daemon: one display (the phone) and at most one running session.

Phone  -> daemon  (/ws/display):  JSON text: hello{token,cols,rows}, resize{cols,rows}
Daemon -> phone:                  binary = raw ANSI bytes; JSON text: reset
CLI    -> daemon  (/ws/session):  JSON text: start{argv,cwd}; binary = keystrokes
Daemon -> CLI:                    binary = output; JSON text: size, exit{code}, error{message}
Web UI -> daemon  (/ws/preview):  JSON text: preview{source,cols,rows}
Daemon -> Web UI:                 binary = raw ANSI frames; JSON text: preview_ready/error
"""

from __future__ import annotations

import asyncio
import json
import re
import secrets
import tomllib
from pathlib import Path
from urllib.parse import quote

import segno
from aiohttp import WSMsgType, web

from . import __version__
from .board import (
    Board,
    board_to_model,
    create_board,
    delete_board,
    duplicate_board,
    list_board_summaries,
    list_boards,
    load_board,
    parse_board_source,
    read_board_source,
    rename_board,
    safe_name,
    save_board_source,
    summarize_board,
)
from .config import DEFAULT_BOARDS, DEFAULT_COLS, DEFAULT_ROWS, DEFAULT_WIDGETS
from .session import Session
from .widgets import load_widget, run_widget, scan_widgets

MAX_DIM = 500
MAX_BOARD_SOURCE = 64 * 1024
MAX_PREVIEW_SOURCE = 64 * 1024
COOKIE_NAME = "ansiko_token"
WEB_DIR = Path(__file__).parent / "web"
INDEX_HTML = (WEB_DIR / "index.html").read_text(encoding="utf-8")
DAEMON_KEY = web.AppKey("daemon", "Daemon")


class Outbox:
    """Ordered, bounded send queue for one websocket.

    Producers are synchronous callbacks (PTY reads), so they enqueue and a pump task
    does the awaiting. A client too slow to keep up is disconnected rather than allowed
    to stall the PTY or silently lose bytes; it recovers by reconnecting (the program is
    asked to redraw on connect).
    """

    def __init__(self, ws: web.WebSocketResponse, maxsize: int = 1024) -> None:
        self.ws = ws
        self.dead = False
        self.queue: asyncio.Queue[tuple[str, object]] = asyncio.Queue(maxsize)
        self.task = asyncio.get_running_loop().create_task(self._pump())
        self._closer: asyncio.Task | None = None

    def send_bytes(self, data: bytes) -> None:
        self._put(("b", data))

    def send_json(self, obj: dict) -> None:
        self._put(("j", obj))

    def close(self) -> None:
        self._put(("c", None))

    def _put(self, item: tuple[str, object]) -> None:
        if self.dead:
            return
        try:
            self.queue.put_nowait(item)
        except asyncio.QueueFull:
            self.dead = True
            self.task.cancel()
            self._closer = asyncio.get_running_loop().create_task(self.ws.close())

    async def _pump(self) -> None:
        try:
            while True:
                kind, payload = await self.queue.get()
                if kind == "b":
                    await self.ws.send_bytes(payload)  # type: ignore[arg-type]
                elif kind == "j":
                    await self.ws.send_json(payload)
                else:
                    await self.ws.close()
                    return
        except (ConnectionError, RuntimeError):
            pass
        finally:
            self.dead = True


def idle_screen(cols: int, rows: int) -> bytes:
    """What the phone shows when nothing is running."""
    row = max(rows // 2, 1)
    title, hint = "ansiko", "waiting for a program"
    col_t = max((cols - len(title)) // 2, 0) + 1
    col_h = max((cols - len(hint)) // 2, 0) + 1
    text = (
        f"\x1b[2J\x1b[H\x1b[?25l"
        f"\x1b[{row};{col_t}H\x1b[1m{title}\x1b[0m"
        f"\x1b[{row + 1};{col_h}H\x1b[2m{hint}\x1b[0m"
    )
    return text.encode()


class Daemon:
    def __init__(
        self,
        token: str,
        boards_dir: Path = Path(DEFAULT_BOARDS),
        widgets_dir: Path = Path(DEFAULT_WIDGETS),
    ) -> None:
        self.token = token
        self.boards_dir = boards_dir
        self.widgets_dir = widgets_dir
        self.display: Outbox | None = None
        self.cols, self.rows = (
            DEFAULT_COLS,
            DEFAULT_ROWS,
        )  # last size the phone reported
        self.session: Session | None = None
        self.owner: Outbox | None = None  # the CLI connection that owns the session
        self.argv: list[str] = []
        self.board: Board | None = None
        self.board_folder: str | None = None

    def check_token(self, candidate: object) -> bool:
        return isinstance(candidate, str) and secrets.compare_digest(
            candidate.encode(), self.token.encode()
        )

    # --- display (the phone) -------------------------------------------------

    def attach_display(self, out: Outbox, cols: int, rows: int) -> None:
        old, self.display = self.display, out
        if old is not None:
            old.close()
        self.cols, self.rows = cols, rows
        out.send_json({"type": "reset"})
        if self.board is not None:
            self.board.set_size(cols, rows)
            self.board.request_render()
        elif self.session is not None:
            self.session.resize(cols, rows)  # SIGWINCH makes the program redraw for us
        else:
            out.send_bytes(idle_screen(cols, rows))
        self._announce_size()

    def set_size(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        if self.board is not None:
            self.board.set_size(cols, rows)
            self.board.request_render()
        elif self.session is not None:
            self.session.resize(cols, rows)
        elif self.display is not None:
            # No program to redraw the idle screen after a rotation.
            self.display.send_json({"type": "reset"})
            self.display.send_bytes(idle_screen(cols, rows))
        self._announce_size()

    def detach_display(self, out: Outbox) -> None:
        if self.display is out:
            self.display = None

    def _announce_size(self) -> None:
        if self.owner is not None:
            self.owner.send_json({"type": "size", "cols": self.cols, "rows": self.rows})

    # --- session -------------------------------------------------------------

    def start_session(self, argv: list[str], cwd: str | None, owner: Outbox) -> None:
        if self.board is not None:
            self.board.stop()
            self.board = None
            self.board_folder = None
        session = Session(
            argv, self.cols, self.rows, self._on_output, self._on_exit, cwd=cwd
        )
        session.start()  # may raise OSError
        self.session, self.owner, self.argv = session, owner, argv
        if self.display is not None:
            self.display.send_json({"type": "reset"})
        self._announce_size()

    def release_session(self, owner: Outbox) -> None:
        """The owning CLI went away (exit key, Ctrl+C on its side, network): end the program."""
        if self.owner is owner and self.session is not None:
            self.owner = None
            self.session.stop()

    def _on_output(self, data: bytes) -> None:
        if self.board is not None:
            return
        for out in (self.display, self.owner):
            if out is not None:
                out.send_bytes(data)

    def _on_exit(self, code: int) -> None:
        if self.owner is not None:
            self.owner.send_json({"type": "exit", "code": code})
            self.owner.close()
        self.session = None
        self.owner = None
        self.argv = []
        if self.board is None and self.display is not None:
            self.display.send_json({"type": "reset"})
            self.display.send_bytes(idle_screen(self.cols, self.rows))

    async def stop_active(self) -> None:
        if self.session is not None:
            self.session.stop()
            for _ in range(20):
                if self.session is None:
                    break
                await asyncio.sleep(0.05)
        self.session = None
        self.owner = None
        self.argv = []
        if self.board is not None:
            self.board.stop()
        self.board = None
        self.board_folder = None
        if self.display is not None:
            self.display.send_json({"type": "reset"})
            self.display.send_bytes(idle_screen(self.cols, self.rows))

    # --- board ---------------------------------------------------------------

    async def activate_board(self, name: str) -> None:
        spec = load_board(name, self.boards_dir, self.widgets_dir)
        if self.session is not None:
            self.session.stop()
            for _ in range(20):
                if self.session is None:
                    break
                await asyncio.sleep(0.05)
            if self.session is not None:
                self.session = None
                self.owner = None
                self.argv = []

        if self.board is not None:
            self.board.stop()
        self.board = Board(
            spec.name,
            spec.widgets,
            self.cols,
            self.rows,
            self._emit_board,
            spec.regions,
            spec.frame,
        )
        self.board_folder = name
        self.board.start()
        if self.display is not None:
            self.display.send_json({"type": "reset"})
            self.board.request_render()

    def _emit_board(self, frame: bytes) -> None:
        if self.board is not None and self.display is not None:
            self.display.send_bytes(frame)

    def note_renamed_board(self, old: str, new: str) -> None:
        if self.board_folder == old:
            self.board_folder = new
            if self.board is not None:
                self.board.name = new

    def note_deleted_board(self, name: str) -> None:
        if self.board_folder == name:
            if self.board is not None:
                self.board.stop()
            self.board = None
            self.board_folder = None
            if self.display is not None:
                self.display.send_json({"type": "reset"})
                self.display.send_bytes(idle_screen(self.cols, self.rows))

    def status(self) -> dict:
        return {
            "version": __version__,
            "display": {
                "connected": self.display is not None,
                "cols": self.cols,
                "rows": self.rows,
            },
            "session": {"running": self.session is not None, "argv": self.argv},
            "board": {
                "active": self.board is not None,
                "name": self.board_folder,
                "title": self.board.name if self.board is not None else None,
                "errors": self.board.errors() if self.board is not None else [],
            },
        }


# --- HTTP / WebSocket handlers -------------------------------------------------


def _parse_size(msg: dict) -> tuple[int, int] | None:
    cols, rows = msg.get("cols"), msg.get("rows")
    if all(
        isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= MAX_DIM
        for v in (cols, rows)
    ):
        return cols, rows
    return None


def _auth_ok(request: web.Request, daemon: Daemon) -> bool:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme == "Bearer" and daemon.check_token(value):
        return True
    return daemon.check_token(request.cookies.get(COOKIE_NAME))


def _toml_error(exc: Exception) -> dict:
    message = str(exc)
    line = getattr(exc, "lineno", None)
    column = getattr(exc, "colno", None)
    if line is None:
        match = re.search(r"at line (\d+), column (\d+)", message)
        if match:
            line, column = int(match.group(1)), int(match.group(2))
            message = re.sub(r" \(at line \d+, column \d+\)$", "", message)
    elif line is not None:
        message = re.sub(r" \(at line \d+, column \d+\)$", "", message)
    return {"error": message, "line": line, "column": column}


def _board_parse_error(exc: Exception) -> dict:
    if isinstance(exc, tomllib.TOMLDecodeError):
        return _toml_error(exc)
    return {"error": str(exc), "line": None, "column": None}


async def display_ws(request: web.Request) -> web.WebSocketResponse:
    daemon: Daemon = request.app[DAEMON_KEY]
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=64 * 1024)
    await ws.prepare(request)

    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except (TimeoutError, ValueError, TypeError):
        await ws.close(code=4400, message=b"bad hello")
        return ws
    if (
        not isinstance(hello, dict)
        or hello.get("type") != "hello"
        or not daemon.check_token(hello.get("token"))
    ):
        await ws.close(code=4401, message=b"unauthorized")
        return ws
    size = _parse_size(hello)
    if size is None:
        await ws.close(code=4400, message=b"bad size")
        return ws

    out = Outbox(ws)
    daemon.attach_display(out, *size)
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                continue
            if isinstance(data, dict) and data.get("type") == "resize":
                new_size = _parse_size(data)
                if new_size is not None:
                    daemon.set_size(*new_size)
    finally:
        daemon.detach_display(out)
        out.close()
    return ws


async def session_ws(request: web.Request) -> web.WebSocketResponse:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=1024 * 1024)
    await ws.prepare(request)

    async def fail(message: str) -> web.WebSocketResponse:
        await ws.send_json({"type": "error", "message": message})
        await ws.close()
        return ws

    try:
        msg = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except (TimeoutError, ValueError, TypeError):
        return await fail("expected a start message")
    if not isinstance(msg, dict):
        return await fail("invalid start message")
    argv = msg.get("argv")
    cwd = msg.get("cwd")
    if (
        msg.get("type") != "start"
        or not isinstance(argv, list)
        or not argv
        or not all(isinstance(a, str) and a for a in argv)
        or not (cwd is None or isinstance(cwd, str))
    ):
        return await fail("invalid start message")
    if daemon.session is not None:
        return await fail("a session is already running")

    out = Outbox(ws)
    try:
        daemon.start_session(argv, cwd, out)
    except OSError as e:
        out.task.cancel()
        return await fail(f"cannot start {argv[0]!r}: {e.strerror or e}")

    try:
        async for m in ws:
            session = daemon.session
            if m.type == WSMsgType.BINARY and daemon.owner is out and session:
                await session.write(m.data)
    finally:
        daemon.release_session(out)
        out.close()
    return ws


async def preview_ws(request: web.Request) -> web.WebSocketResponse:
    daemon: Daemon = request.app[DAEMON_KEY]
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_PREVIEW_SOURCE * 2)
    await ws.prepare(request)
    if not _auth_ok(request, daemon):
        await ws.close(code=4401, message=b"unauthorized")
        return ws

    out = Outbox(ws, maxsize=512)
    board: Board | None = None
    try:
        async for msg in ws:
            if msg.type != WSMsgType.TEXT:
                continue
            try:
                data = json.loads(msg.data)
            except ValueError:
                out.send_json({"type": "preview_error", "error": "invalid JSON"})
                continue
            if not isinstance(data, dict) or data.get("type") != "preview":
                continue
            source = data.get("source")
            size = _parse_size(data)
            if not isinstance(source, str):
                out.send_json(
                    {"type": "preview_error", "error": "source must be a string"}
                )
                continue
            if len(source) > MAX_PREVIEW_SOURCE:
                out.send_json(
                    {"type": "preview_error", "error": "board source is too large"}
                )
                continue
            if size is None:
                out.send_json(
                    {
                        "type": "preview_error",
                        "error": f"cols and rows must be 1..{MAX_DIM}",
                    }
                )
                continue

            if board is not None:
                board.stop()
                board = None
            try:
                spec = parse_board_source(source, "preview", daemon.widgets_dir)
                board = Board(
                    spec.name,
                    spec.widgets,
                    size[0],
                    size[1],
                    out.send_bytes,
                    spec.regions,
                    spec.frame,
                )
                board.start()
                out.send_bytes(b"\x1b[2J\x1b[H\x1b[?25l")
                out.send_json({"type": "preview_ready"})
            except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as e:
                details = _board_parse_error(e)
                out.send_json({"type": "preview_error", **details})
    finally:
        if board is not None:
            board.stop()
        out.close()
    return ws


async def api_session(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    return web.json_response({"authenticated": _auth_ok(request, daemon)})


async def api_status(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    return web.json_response(daemon.status())


async def api_push(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    name = data.get("board") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name:
        raise web.HTTPBadRequest(text="expected a board name")

    try:
        await daemon.activate_board(name)
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except (OSError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.json_response(daemon.status())


async def api_stop(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    await daemon.stop_active()
    return web.json_response(daemon.status())


async def api_widgets(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    widgets, errors = scan_widgets(daemon.widgets_dir)
    return web.json_response(
        {"widgets": [widget.to_dict() for widget in widgets], "errors": errors}
    )


async def api_widget_run(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="invalid request")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise web.HTTPBadRequest(text="expected a widget name")
    try:
        widget = load_widget(daemon.widgets_dir / safe_name(name))
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except (OSError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    cols, rows = data.get("cols"), data.get("rows")
    output, error = await run_widget(
        widget,
        cols
        if isinstance(cols, int) and not isinstance(cols, bool) and 1 <= cols <= MAX_DIM
        else None,
        rows
        if isinstance(rows, int) and not isinstance(rows, bool) and 1 <= rows <= MAX_DIM
        else None,
    )
    return web.json_response({"output": output, "error": error})


async def api_boards(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    if request.query.get("details") in ("1", "true", "yes"):
        summaries = list_board_summaries(daemon.boards_dir, daemon.widgets_dir)
        for summary in summaries:
            summary["active"] = summary["name"] == daemon.board_folder
        return web.json_response(summaries)
    return web.json_response(list_boards(daemon.boards_dir))


async def api_board_get(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        source = read_board_source(request.match_info["name"], daemon.boards_dir)
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except ValueError as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.Response(text=source, content_type="text/plain")


async def api_board_put(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    source = await request.text()
    if len(source) > MAX_BOARD_SOURCE:
        raise web.HTTPRequestEntityTooLarge(
            max_size=MAX_BOARD_SOURCE, actual_size=len(source)
        )
    try:
        title = save_board_source(
            request.match_info["name"], source, daemon.boards_dir, daemon.widgets_dir
        )
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.json_response({"name": request.match_info["name"], "title": title})


async def api_board_validate(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="invalid request")
    source = data.get("source")
    name = data.get("name", "preview")
    if not isinstance(source, str):
        raise web.HTTPBadRequest(text="expected board source")
    if len(source) > MAX_BOARD_SOURCE:
        raise web.HTTPRequestEntityTooLarge(
            max_size=MAX_BOARD_SOURCE, actual_size=len(source)
        )
    if not isinstance(name, str) or not name:
        name = "preview"
    try:
        safe_name(name)
    except ValueError as e:
        return web.json_response({"ok": False, "error": str(e)}, status=400)
    try:
        spec = parse_board_source(source, name, daemon.widgets_dir)
    except (OSError, TypeError, ValueError, tomllib.TOMLDecodeError) as e:
        return web.json_response({"ok": False, **_board_parse_error(e)}, status=400)
    return web.json_response({"ok": True, "model": board_to_model(spec, name)})


async def api_board_create(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(text="invalid request")
    name = data.get("name")
    template = data.get("template", "auto")
    frame = data.get("frame", False)
    widget_names = data.get("widgets")
    if not isinstance(name, str):
        raise web.HTTPBadRequest(text="expected a board name")
    if template not in ("auto", "single", "columns", "grid"):
        raise web.HTTPBadRequest(text="unknown board template")
    if not isinstance(frame, bool):
        raise web.HTTPBadRequest(text="frame must be a boolean")
    if widget_names is not None and (
        not isinstance(widget_names, list)
        or not all(isinstance(item, str) and item for item in widget_names)
    ):
        raise web.HTTPBadRequest(text="widgets must be a list of names")
    try:
        create_board(
            name,
            daemon.boards_dir,
            daemon.widgets_dir,
            template=template,
            widget_names=widget_names,
            frame=frame,
        )
    except FileExistsError as e:
        raise web.HTTPConflict(text=str(e)) from None
    except (OSError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.json_response(
        {
            "name": name,
            "board": summarize_board(name, daemon.boards_dir, daemon.widgets_dir),
        },
        status=201,
    )


async def api_board_delete(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    name = request.match_info["name"]
    try:
        if daemon.board_folder == name:
            await daemon.stop_active()
        delete_board(name, daemon.boards_dir)
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except (OSError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.json_response({"ok": True, "name": name})


async def api_board_duplicate(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    new_name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(new_name, str) or not new_name:
        raise web.HTTPBadRequest(text="expected a new board name")
    try:
        duplicate_board(
            request.match_info["name"],
            new_name,
            daemon.boards_dir,
            daemon.widgets_dir,
        )
    except FileExistsError as e:
        raise web.HTTPConflict(text=str(e)) from None
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except (OSError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.json_response(
        {
            "name": new_name,
            "board": summarize_board(new_name, daemon.boards_dir, daemon.widgets_dir),
        },
        status=201,
    )


async def api_board_rename(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    new_name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(new_name, str) or not new_name:
        raise web.HTTPBadRequest(text="expected a new board name")
    old_name = request.match_info["name"]
    try:
        rename_board(old_name, new_name, daemon.boards_dir)
        daemon.note_renamed_board(old_name, new_name)
    except FileExistsError as e:
        raise web.HTTPConflict(text=str(e)) from None
    except FileNotFoundError as e:
        raise web.HTTPNotFound(text=str(e)) from None
    except (OSError, TypeError, ValueError) as e:
        raise web.HTTPBadRequest(text=str(e)) from None
    return web.json_response(
        {
            "name": new_name,
            "board": summarize_board(new_name, daemon.boards_dir, daemon.widgets_dir),
        }
    )


async def index(request: web.Request) -> web.Response:
    return web.Response(
        text=INDEX_HTML,
        content_type="text/html",
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


async def api_login(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    try:
        data = json.loads(await request.text())
    except ValueError:
        raise web.HTTPBadRequest(text="invalid JSON") from None
    token = data.get("token") if isinstance(data, dict) else None
    if not daemon.check_token(token):
        raise web.HTTPUnauthorized(text="wrong token")
    response = web.json_response({"ok": True})
    response.set_cookie(
        COOKIE_NAME, daemon.token, httponly=True, samesite="Strict", path="/"
    )
    return response


async def api_logout(request: web.Request) -> web.Response:
    response = web.json_response({"ok": True})
    response.del_cookie(COOKIE_NAME, path="/")
    return response


def _pair_url(request: web.Request, daemon: Daemon) -> str:
    host = request.url.host
    port = request.url.port or 80
    return (
        f"ansiko://pair?host={quote(host, safe='')}"
        f"&port={port}&token={quote(daemon.token, safe='')}"
    )


async def api_pair(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    return web.json_response({"url": _pair_url(request, daemon)})


async def api_pair_svg(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _auth_ok(request, daemon):
        raise web.HTTPUnauthorized()
    qr = segno.make(_pair_url(request, daemon), error="m")
    return web.Response(text=qr.svg_inline(), content_type="image/svg+xml")


async def _cleanup(app: web.Application) -> None:
    daemon: Daemon = app[DAEMON_KEY]
    if daemon.board is not None:
        daemon.board.stop()
    if daemon.session is not None:
        daemon.session.stop()
        await asyncio.sleep(0.2)


def create_app(
    token: str,
    boards_dir: Path = Path(DEFAULT_BOARDS),
    widgets_dir: Path = Path(DEFAULT_WIDGETS),
) -> web.Application:
    app = web.Application()
    app[DAEMON_KEY] = Daemon(token, Path(boards_dir), Path(widgets_dir))
    app.add_routes(
        [
            web.get("/", index),
            web.get("/ws/display", display_ws),
            web.get("/ws/session", session_ws),
            web.get("/ws/preview", preview_ws),
            web.get("/api/session", api_session),
            web.get("/api/status", api_status),
            web.post("/api/push", api_push),
            web.post("/api/stop", api_stop),
            web.post("/api/login", api_login),
            web.post("/api/logout", api_logout),
            web.get("/api/pair", api_pair),
            web.get("/api/pair.svg", api_pair_svg),
            web.get("/api/widgets", api_widgets),
            web.post("/api/widgets/run", api_widget_run),
            web.get("/api/boards", api_boards),
            web.post("/api/boards", api_board_create),
            web.post("/api/boards/validate", api_board_validate),
            web.get("/api/boards/{name}", api_board_get),
            web.put("/api/boards/{name}", api_board_put),
            web.delete("/api/boards/{name}", api_board_delete),
            web.post("/api/boards/{name}/duplicate", api_board_duplicate),
            web.post("/api/boards/{name}/rename", api_board_rename),
        ]
    )
    if WEB_DIR.is_dir():
        app.router.add_static("/static/", WEB_DIR, name="static", show_index=False)
    app.on_cleanup.append(_cleanup)
    return app


def serve(
    host: str,
    port: int,
    token: str,
    boards_dir: Path = Path(DEFAULT_BOARDS),
    widgets_dir: Path = Path(DEFAULT_WIDGETS),
) -> None:
    web.run_app(
        create_app(token, boards_dir, widgets_dir),
        host=host,
        port=port,
        print=None,
    )
