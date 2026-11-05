"""Thin CLI client for the ansiko daemon."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import sys
import termios
import tty
from pathlib import Path

from . import __version__
from .config import (
    CONFIG_NAME,
    DEFAULT_BOARDS,
    DEFAULT_CUSTOM_BOARDS,
    DEFAULT_CUSTOM_WIDGETS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_WIDGETS,
    default_dir,
    load_config,
    user_data_dir,
)

TOKEN_ENV = "ANSIKO_TOKEN"


def _load(args: argparse.Namespace) -> tuple[dict, Path | None, str, int, str | None]:
    data, path = load_config(args.config)
    host = args.host or data.get("host") or DEFAULT_HOST
    port = args.port if args.port is not None else data.get("port", DEFAULT_PORT)
    token = args.token or data.get("token") or os.environ.get(TOKEN_ENV)

    if not isinstance(host, str) or not host.strip():
        raise SystemExit("error: host must be a non-empty string")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise SystemExit("error: port must be 1..65535")
    if token is not None and not isinstance(token, str):
        raise SystemExit("error: token must be a string")
    return data, path, host.strip(), port, token or None


def _require_token(token: str | None) -> str:
    if not token:
        raise SystemExit(
            f"error: pass --token, set {TOKEN_ENV}, or put it in {CONFIG_NAME}"
        )
    return token


def _directory(value: object, default: str, base: Path) -> Path:
    if value is None:
        local = base / default
        if local.is_dir():
            return local
        if default in (DEFAULT_BOARDS, DEFAULT_WIDGETS):
            return default_dir(default)
        # Installed tools must not create custom content inside site-packages
        # or in a random working directory.
        return user_data_dir() / default
    if not isinstance(value, str) or not value.strip():
        raise SystemExit("error: board/widget paths must be non-empty strings")
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _serve(args: argparse.Namespace) -> int:
    data, path, host, port, token = _load(args)
    if token is None:
        token = secrets.token_urlsafe(24)
        print(f"token: {token}", file=sys.stderr)

    base = path.parent if path is not None else Path.cwd()
    boards = _directory(args.boards or data.get("boards"), DEFAULT_BOARDS, base)
    widgets = _directory(args.widgets or data.get("widgets"), DEFAULT_WIDGETS, base)
    custom_widgets = _directory(
        args.custom_widgets or data.get("custom_widgets"),
        DEFAULT_CUSTOM_WIDGETS,
        base,
    )
    custom_boards = _directory(
        args.custom_boards or data.get("custom_boards"),
        DEFAULT_CUSTOM_BOARDS,
        base,
    )

    print(
        f"ansiko {__version__} on ws://{host}:{port}/ws/display",
        file=sys.stderr,
        flush=True,
    )
    from .daemon import serve

    serve(host, port, token, boards, widgets, custom_widgets, custom_boards)
    return 0


async def _status(args: argparse.Namespace) -> int:
    import aiohttp

    _, _, host, port, token = _load(args)
    headers = {"Authorization": f"Bearer {_require_token(token)}"}
    async with (
        aiohttp.ClientSession() as http,
        http.get(f"http://{host}:{port}/api/status", headers=headers) as r,
    ):
        text = await r.text()
        if r.status != 200:
            print(f"ansiko: HTTP {r.status}: {text}", file=sys.stderr)
            return 1
        print(json.dumps(json.loads(text), indent=2))
        return 0


async def _push(args: argparse.Namespace) -> int:
    import aiohttp

    _, _, host, port, token = _load(args)
    headers = {"Authorization": f"Bearer {_require_token(token)}"}
    async with (
        aiohttp.ClientSession() as http,
        http.post(
            f"http://{host}:{port}/api/push",
            headers=headers,
            json={"board": args.board},
        ) as r,
    ):
        text = await r.text()
        if r.status != 200:
            print(f"ansiko: HTTP {r.status}: {text}", file=sys.stderr)
            return 1
        body = json.loads(text)
        print(f"pushed board: {body['board']['name']}")
        return 0


async def _run(args: argparse.Namespace) -> int:
    import aiohttp

    _, _, host, port, token = _load(args)
    headers = {"Authorization": f"Bearer {_require_token(token)}"}
    async with (
        aiohttp.ClientSession() as http,
        http.ws_connect(
            f"ws://{host}:{port}/ws/session", headers=headers, heartbeat=20
        ) as ws,
    ):
        await ws.send_json({"type": "start", "argv": args.argv, "cwd": args.cwd})

        stdin_fd = sys.stdin.fileno()
        old_term = None
        if sys.stdin.isatty():
            old_term = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)

        loop = asyncio.get_running_loop()
        sends: set[asyncio.Task] = set()

        def on_stdin() -> None:
            try:
                data = os.read(stdin_fd, 4096)
            except OSError:
                data = b""
            if not data:
                loop.remove_reader(stdin_fd)
                return
            task = asyncio.create_task(ws.send_bytes(data))
            sends.add(task)
            task.add_done_callback(sends.discard)

        reader_added = False
        remote_exit: int | None = None
        try:
            try:
                loop.add_reader(stdin_fd, on_stdin)
                reader_added = True
            except (OSError, ValueError):
                pass  # stdin is not pollable (for example /dev/null)
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    sys.stdout.buffer.write(msg.data)
                    sys.stdout.buffer.flush()
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    update = json.loads(msg.data)
                    if update.get("type") == "error":
                        print(
                            f"\r\nansiko: {update.get('message')}",
                            file=sys.stderr,
                            flush=True,
                        )
                        break
                    if update.get("type") == "exit":
                        code = update.get("code")
                        remote_exit = code if isinstance(code, int) else 1
                        break
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSE,
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                ):
                    break
        finally:
            if reader_added:
                loop.remove_reader(stdin_fd)
            if old_term is not None:
                termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_term)
            for task in sends:
                task.cancel()
    if remote_exit is not None:
        # Match shell conventions for a program killed by a signal.
        return remote_exit if remote_exit >= 0 else 128 - remote_exit
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ansiko")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="action", required=True)

    def add_connection(p: argparse.ArgumentParser) -> None:
        p.add_argument("--host", default=None)
        p.add_argument("--port", type=int, default=None)
        p.add_argument("--token", help=f"server token (default: ${TOKEN_ENV})")
        p.add_argument("--config", help=f"TOML config (default: {CONFIG_NAME})")

    p_serve = sub.add_parser("serve", help="start the daemon")
    add_connection(p_serve)
    p_serve.add_argument("--boards", help="board directory")
    p_serve.add_argument("--widgets", help="bundled widget directory")
    p_serve.add_argument("--custom-widgets", help="custom widget directory")
    p_serve.add_argument("--custom-boards", help="custom board directory")

    p_run = sub.add_parser("run", help="run a program on the phone until it exits")
    add_connection(p_run)
    p_run.add_argument("--cwd")
    p_run.add_argument("argv", nargs=argparse.REMAINDER)

    p_push = sub.add_parser("push", help="show a saved board")
    add_connection(p_push)
    p_push.add_argument("board")

    p_status = sub.add_parser("status", help="show the display and current mode")
    add_connection(p_status)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.action == "run":
        if args.argv and args.argv[0] == "--":
            args.argv = args.argv[1:]
        if not args.argv:
            parser.error("run needs a command, for example: ansiko run fastfetch")
    try:
        if args.action == "serve":
            return _serve(args)
        if args.action == "status":
            return asyncio.run(_status(args))
        if args.action == "push":
            return asyncio.run(_push(args))
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except Exception as e:  # noqa: BLE001 - CLI boundary
        print(f"ansiko: {e}", file=sys.stderr)
        return 1
