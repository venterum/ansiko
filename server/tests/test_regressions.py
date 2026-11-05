from __future__ import annotations

import argparse
import asyncio
import io
import sys
from pathlib import Path

from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from ansiko import cli
from ansiko.daemon import create_app
from ansiko.widgets import load_widget, run_widget

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def write_widget(directory: Path) -> None:
    directory.mkdir(parents=True)
    script = directory / "run.sh"
    script.write_text("#!/bin/sh\nprintf 'clock\\n'\n")
    script.chmod(0o755)
    (directory / "widget.toml").write_text(
        'name = "clock"\n'
        'command = "./run.sh"\n'
        "interval = 1\n"
        "width = 20\n"
        "height = 3\n"
        "timeout = 2\n"
    )


def write_board(directory: Path) -> None:
    directory.mkdir(parents=True)
    (directory / "board.toml").write_text('name = "demo"\nwidgets = ["clock"]\n')


async def hello(ws, cols: int = 40, rows: int = 10) -> None:
    await ws.send_json({"type": "hello", "token": TOKEN, "cols": cols, "rows": rows})


async def collect_until(ws, marker: bytes, timeout: float = 4.0) -> bytes:
    output = b""
    deadline = asyncio.get_running_loop().time() + timeout
    while marker not in output:
        left = deadline - asyncio.get_running_loop().time()
        if left <= 0:
            break
        message = await asyncio.wait_for(ws.receive(), left)
        if message.type == WSMsgType.BINARY:
            output += message.data
        elif message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
            break
    return output


async def test_reconnect_at_same_size_requests_a_redraw():
    app = create_app(TOKEN)
    async with TestClient(TestServer(app)) as client:
        display = await client.ws_connect("/ws/display")
        await hello(display)
        cli_ws = await client.ws_connect("/ws/session", headers=AUTH)
        script = 'trap "echo WINCH" WINCH; echo READY; while :; do sleep 0.2; done'
        await cli_ws.send_json(
            {"type": "start", "argv": ["/bin/sh", "-c", script], "cwd": None}
        )
        assert b"READY" in await collect_until(cli_ws, b"READY")
        await display.close()
        await asyncio.sleep(0.2)

        display = await client.ws_connect("/ws/display")
        await hello(display)
        # The server sends a reset text frame first; the shell's trap proves that
        # the foreground process group also received SIGWINCH at the same size.
        assert b"WINCH" in await collect_until(display, b"WINCH")
        await cli_ws.close()
        await display.close()


async def test_failed_session_start_keeps_the_active_board(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock")
    write_board(boards / "demo")
    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        pushed = await client.post("/api/push", json={"board": "demo"}, headers=AUTH)
        assert pushed.status == 200
        assert (await pushed.json())["board"]["active"] is True

        ws = await client.ws_connect("/ws/session", headers=AUTH)
        await ws.send_json(
            {"type": "start", "argv": ["/bin/true"], "cwd": "/does/not/exist"}
        )
        message = await asyncio.wait_for(ws.receive(), 3)
        assert message.type == WSMsgType.TEXT
        assert message.json()["type"] == "error"
        await ws.close()

        status = await (await client.get("/api/status", headers=AUTH)).json()
        assert status["board"]["active"] is True
        assert status["board"]["name"] == "demo"


async def test_cli_returns_remote_exit_code(tmp_path, monkeypatch):
    app = create_app(TOKEN)
    async with TestClient(TestServer(app)) as client:
        stdin_path = tmp_path / "stdin"
        stdin_path.write_bytes(b"")
        stdin = stdin_path.open("rb")
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        monkeypatch.setattr(sys, "stdin", stdin)
        monkeypatch.setattr(sys, "stdout", stdout)
        args = argparse.Namespace(
            host="127.0.0.1",
            port=client.server.port,
            token=TOKEN,
            argv=["/bin/sh", "-c", "exit 7"],
            cwd=None,
            config=None,
        )
        try:
            assert await cli._run(args) == 7
        finally:
            stdin.close()


async def test_invalid_board_returns_400_not_404(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock")
    write_board(boards / "demo")
    (boards / "bad").mkdir()
    (boards / "bad" / "board.toml").write_text('name = "bad"\nwidgets = ["missing"]\n')
    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        put = await client.put(
            "/api/boards/demo",
            data='name = "demo"\nwidgets = ["missing"]\n',
            headers=AUTH,
        )
        assert put.status == 400
        push = await client.post("/api/push", json={"board": "bad"}, headers=AUTH)
        assert push.status == 400


async def test_python_widget_works_without_exec_bit(tmp_path):
    directory = tmp_path / "plain"
    directory.mkdir()
    script = directory / "run.py"
    script.write_text("#!/usr/bin/env python3\nprint('packaged-ok')\n")
    script.chmod(0o644)
    (directory / "widget.toml").write_text(
        'name = "plain"\ncommand = "./run.py"\ninterval = 1\ntimeout = 2\n'
    )
    output, error = await run_widget(load_widget(directory))
    assert error is None
    assert output == "packaged-ok"


async def test_cli_returns_one_for_start_error(tmp_path, monkeypatch):
    app = create_app(TOKEN)
    async with TestClient(TestServer(app)) as client:
        stdin_path = tmp_path / "stdin"
        stdin_path.write_bytes(b"")
        stdin = stdin_path.open("rb")
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        monkeypatch.setattr(sys, "stdin", stdin)
        monkeypatch.setattr(sys, "stdout", stdout)
        args = argparse.Namespace(
            host="127.0.0.1",
            port=client.server.port,
            token=TOKEN,
            argv=["/bin/true"],
            cwd="/does/not/exist",
            config=None,
        )
        try:
            assert await cli._run(args) == 1
        finally:
            stdin.close()
