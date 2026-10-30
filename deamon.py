"""The ansiko daemon: one display (the phone) and at most one running session.

Phone  -> daemon  (/ws/display):  JSON text: hello{token,cols,rows}, resize{cols,rows}
Daemon -> phone:                  binary = raw ANSI bytes; JSON text: reset
CLI    -> daemon  (/ws/session):  JSON text: start{argv,cwd}; binary = keystrokes
Daemon -> CLI:                    binary = output; JSON text: size, exit{code}, error{message}
"""

from __future__ import annotations

import asyncio
import json
import secrets

from aiohttp import WSMsgType, web

from . import __version__
from .config import DEFAULT_COLS, DEFAULT_ROWS
from .session import Session

MAX_DIM = 500
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
        except ConnectionError:
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
    def __init__(self, token: str) -> None:
        self.token = token
        self.display: Outbox | None = None
        self.cols, self.rows = DEFAULT_COLS, DEFAULT_ROWS  # last size the phone reported
        self.session: Session | None = None
        self.owner: Outbox | None = None  # the CLI connection that owns the session
        self.argv: list[str] = []

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
        if self.session is not None:
            self.session.resize(cols, rows)  # SIGWINCH makes the program redraw for us
        else:
            out.send_bytes(idle_screen(cols, rows))
        self._announce_size()

    def set_size(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        if self.session is not None:
            self.session.resize(cols, rows)
        self._announce_size()

    def detach_display(self, out: Outbox) -> None:
        if self.display is out:
            self.display = None

    def _announce_size(self) -> None:
        if self.owner is not None:
            self.owner.send_json({"type": "size", "cols": self.cols, "rows": self.rows})

    # --- session -------------------------------------------------------------

    def start_session(self, argv: list[str], cwd: str | None, owner: Outbox) -> None:
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


def _bearer_ok(request: web.Request, daemon: Daemon) -> bool:
    header = request.headers.get("Authorization", "")
    scheme, _, value = header.partition(" ")
    return scheme == "Bearer" and daemon.check_token(value)


async def display_ws(request: web.Request) -> web.WebSocketResponse:
    daemon: Daemon = request.app[DAEMON_KEY]
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=64 * 1024)
    await ws.prepare(request)

    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except (asyncio.TimeoutError, ValueError, TypeError):
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
    if not _bearer_ok(request, daemon):
        raise web.HTTPUnauthorized()
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=1024 * 1024)
    await ws.prepare(request)

    async def fail(message: str) -> web.WebSocketResponse:
        await ws.send_json({"type": "error", "message": message})
        await ws.close()
        return ws

    try:
        msg = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except (asyncio.TimeoutError, ValueError, TypeError):
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
            if m.type == WSMsgType.BINARY and daemon.owner is out and daemon.session:
                await daemon.session.write(m.data)
    finally:
        daemon.release_session(out)
        out.close()
    return ws


async def api_status(request: web.Request) -> web.Response:
    daemon: Daemon = request.app[DAEMON_KEY]
    if not _bearer_ok(request, daemon):
        raise web.HTTPUnauthorized()
    return web.json_response(daemon.status())


async def _cleanup(app: web.Application) -> None:
    daemon: Daemon = app[DAEMON_KEY]
    if daemon.session is not None:
        daemon.session.stop()
        await asyncio.sleep(0.2)


def create_app(token: str) -> web.Application:
    app = web.Application()
    app[DAEMON_KEY] = Daemon(token)
    app.add_routes(
        [
            web.get("/ws/display", display_ws),
            web.get("/ws/session", session_ws),
            web.get("/api/status", api_status),
        ]
    )
    app.on_cleanup.append(_cleanup)
    return app


def serve(host: str, port: int, token: str) -> None:
    web.run_app(create_app(token), host=host, port=port, print=None)
