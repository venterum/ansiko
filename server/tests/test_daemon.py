from __future__ import annotations

import asyncio
import json

from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from ansiko.daemon import DAEMON_KEY, create_app

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


async def recv(ws, timeout: float = 3.0):
    return await asyncio.wait_for(ws.receive(), timeout)


async def attach_display(client: TestClient, cols: int = 40, rows: int = 10):
    ws = await client.ws_connect("/ws/display")
    await ws.send_json({"type": "hello", "token": TOKEN, "cols": cols, "rows": rows})
    reset = await recv(ws)
    idle = await recv(ws)
    assert reset.type == WSMsgType.TEXT
    assert json.loads(reset.data) == {"type": "reset"}
    assert idle.type == WSMsgType.BINARY
    assert b"ansiko" in idle.data
    return ws


async def start_cli(client: TestClient, argv: list[str], cwd: str | None = None):
    ws = await client.ws_connect("/ws/session", headers=AUTH)
    await ws.send_json({"type": "start", "argv": argv, "cwd": cwd})
    return ws


async def test_display_hello_idle_and_resize():
    async with TestClient(TestServer(create_app(TOKEN))) as client:
        ws = await attach_display(client)
        daemon = client.server.app[DAEMON_KEY]
        assert daemon.status()["display"] == {
            "connected": True,
            "cols": 40,
            "rows": 10,
        }

        await ws.send_json({"type": "resize", "cols": 50, "rows": 12})
        reset = await recv(ws)
        idle = await recv(ws)
        assert json.loads(reset.data) == {"type": "reset"}
        assert idle.type == WSMsgType.BINARY
        assert daemon.cols == 50 and daemon.rows == 12
        await ws.close()


async def test_display_rejects_wrong_token():
    async with TestClient(TestServer(create_app(TOKEN))) as client:
        ws = await client.ws_connect("/ws/display")
        await ws.send_json({"type": "hello", "token": "wrong", "cols": 40, "rows": 10})
        msg = await recv(ws)
        assert msg.type == WSMsgType.CLOSE
        assert ws.close_code == 4401


async def test_display_rejects_invalid_size():
    async with TestClient(TestServer(create_app(TOKEN))) as client:
        ws = await client.ws_connect("/ws/display")
        await ws.send_json({"type": "hello", "token": TOKEN, "cols": 0, "rows": 10})
        msg = await recv(ws)
        assert msg.type == WSMsgType.CLOSE
        assert ws.close_code == 4400


async def test_pty_uses_display_grid_and_output_reaches_display():
    async with TestClient(TestServer(create_app(TOKEN))) as client:
        display = await attach_display(client, cols=40, rows=10)
        cli = await start_cli(
            client, ["/bin/sh", "-c", "sleep 0.2; stty size; printf done"]
        )

        output = b""
        for _ in range(20):
            msg = await recv(display)
            if msg.type == WSMsgType.BINARY:
                output += msg.data
            if b"done" in output:
                break
        assert b"10 40" in output
        assert b"done" in output
        await cli.close()
        await display.close()


async def test_cli_keystrokes_reach_pty():
    async with TestClient(TestServer(create_app(TOKEN))) as client:
        cli = await start_cli(client, ["/bin/sh"])
        await cli.send_bytes(b"printf kbd-ok\\n")

        output = b""
        for _ in range(20):
            msg = await recv(cli)
            if msg.type == WSMsgType.BINARY:
                output += msg.data
            if b"kbd-ok" in output:
                break
        assert b"kbd-ok" in output
        await cli.close()


async def test_status_requires_bearer():
    async with TestClient(TestServer(create_app(TOKEN))) as client:
        unauthorized = await client.get("/api/status")
        assert unauthorized.status == 401

        response = await client.get("/api/status", headers=AUTH)
        assert response.status == 200
        body = await response.json()
        assert body["display"]["connected"] is False
        assert body["session"]["running"] is False
