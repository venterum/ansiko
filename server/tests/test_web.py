from __future__ import annotations

import asyncio
from pathlib import Path

from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from ansiko.daemon import create_app

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def write_widget(directory: Path, description: str = "") -> None:
    directory.mkdir(parents=True)
    script = directory / "run.sh"
    script.write_text("#!/bin/sh\nprintf 'web-ok\\n'\n")
    script.chmod(0o755)
    (directory / "widget.toml").write_text(
        f'name = "{directory.name}"\n'
        f'description = "{description}"\n'
        'command = "./run.sh"\n'
        "interval = 1\n"
        "width = 20\n"
        "height = 3\n"
        "timeout = 2\n"
    )


def write_board(directory: Path) -> None:
    directory.mkdir(parents=True)
    (directory / "board.toml").write_text('name = "demo"\nwidgets = ["clock"]\n')


async def test_web_login_boards_save_pair_and_push(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock", "Clock widget")
    write_widget(widgets / "calendar", "Calendar widget")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        page = await client.get("/")
        assert page.status == 200
        assert "Pair phone" in await page.text()

        assert (await client.get("/api/boards")).status == 401
        assert (await client.get("/api/pair")).status == 401
        session = await (await client.get("/api/session")).json()
        assert session == {"authenticated": False}

        wrong = await client.post("/api/login", json={"token": "wrong"})
        assert wrong.status == 401

        login = await client.post("/api/login", json={"token": TOKEN})
        assert login.status == 200
        assert (await (await client.get("/api/session")).json()) == {
            "authenticated": True
        }

        boards_response = await client.get("/api/boards")
        assert boards_response.status == 200
        assert await boards_response.json() == ["demo"]

        source = await client.get("/api/boards/demo")
        assert source.status == 200
        assert 'widgets = ["clock"]' in await source.text()

        update = await client.put(
            "/api/boards/demo",
            data='name = "demo"\nwidgets = ["clock"]\n',
        )
        assert update.status == 200

        widgets = await (await client.get("/api/widgets")).json()
        by_id = {widget["id"]: widget for widget in widgets["widgets"]}
        assert by_id["clock"]["description"] == "Clock widget"
        assert widgets["errors"] == []

        details = await (await client.get("/api/boards?details=1")).json()
        assert details[0]["name"] == "demo"
        assert details[0]["valid"] is True
        assert details[0]["mode"] == "auto"

        valid = await client.post(
            "/api/boards/validate",
            json={"source": 'name = "demo"\nwidgets = ["clock"]\n', "name": "demo"},
        )
        assert valid.status == 200
        assert (await valid.json())["model"]["mode"] == "auto"

        bad = await client.post(
            "/api/boards/validate",
            json={"source": 'name = "demo"\nwidgets = ["missing"]\n', "name": "demo"},
        )
        assert bad.status == 400
        assert "missing" in (await bad.json())["error"]

        created = await client.post(
            "/api/boards",
            json={
                "name": "second",
                "template": "columns",
                "widgets": ["clock", "calendar"],
            },
        )
        assert created.status == 201
        assert (await created.json())["board"]["mode"] == "cells"
        assert "second" in await (await client.get("/api/boards")).json()

        duplicated = await client.post(
            "/api/boards/second/duplicate", json={"name": "third"}
        )
        assert duplicated.status == 201
        renamed = await client.post("/api/boards/third/rename", json={"name": "fourth"})
        assert renamed.status == 200
        assert (await client.get("/api/boards/fourth")).status == 200
        deleted = await client.delete("/api/boards/fourth")
        assert deleted.status == 200
        assert (await client.get("/api/boards/fourth")).status == 404

        widget_run = await client.post(
            "/api/widgets/run", json={"name": "clock", "cols": 10, "rows": 2}
        )
        assert widget_run.status == 200
        assert (await widget_run.json())["output"] == "web-ok"

        for asset in (
            "/static/app.css",
            "/static/app.js",
            "/static/editor.js",
            "/static/ansi.js",
            "/static/favicon.svg",
        ):
            response = await client.get(asset)
            assert response.status == 200, asset

        pair = await (await client.get("/api/pair")).json()
        assert pair["url"].startswith("ansiko://pair?")
        assert f"token={TOKEN}" in pair["url"]

        qr = await client.get("/api/pair.svg")
        assert qr.status == 200
        assert qr.content_type.startswith("image/svg+xml")
        assert "<svg" in await qr.text()

        pushed = await client.post("/api/push", json={"board": "demo"})
        assert pushed.status == 200
        assert (await pushed.json())["board"]["active"] is True

        stopped = await client.post("/api/stop")
        assert stopped.status == 200
        stopped_status = await stopped.json()
        assert stopped_status["board"]["active"] is False
        assert stopped_status["display"]["connected"] is False


async def test_web_rejects_invalid_board_source(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock", "Clock widget")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/login", json={"token": TOKEN})
        bad = await client.put(
            "/api/boards/demo",
            data='name = "demo"\nwidgets = ["missing"]\n',
        )
        assert bad.status in (400, 404)


async def test_web_preview_ws(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock", "Clock widget")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/login", json={"token": TOKEN})
        ws = await client.ws_connect("/ws/preview", headers=AUTH)
        await ws.send_json(
            {
                "type": "preview",
                "source": 'name = "demo"\nwidgets = ["clock"]\n',
                "cols": 30,
                "rows": 8,
            }
        )
        ready = False
        frame = b""
        for _ in range(80):
            message = await asyncio.wait_for(ws.receive(), 2)
            if message.type == WSMsgType.TEXT:
                payload = message.json()
                if payload.get("type") == "preview_ready":
                    ready = True
                if payload.get("type") == "preview_error":
                    raise AssertionError(payload)
            elif message.type == WSMsgType.BINARY:
                frame += message.data
            if ready and b"web-ok" in frame:
                break
        assert ready
        assert b"web-ok" in frame
        await ws.close()


async def test_web_preview_rejects_bad_source_and_auth(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock", "Clock widget")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        ws = await client.ws_connect("/ws/preview")
        message = await asyncio.wait_for(ws.receive(), 2)
        assert message.type == WSMsgType.CLOSE
        assert ws.close_code == 4401

        await client.post("/api/login", json={"token": TOKEN})
        ws = await client.ws_connect("/ws/preview", headers=AUTH)
        await ws.send_json(
            {
                "type": "preview",
                "source": 'name = "x"\nwidgets = [clock]',
                "cols": 30,
                "rows": 8,
            }
        )
        message = await asyncio.wait_for(ws.receive(), 2)
        assert message.type == WSMsgType.TEXT
        payload = message.json()
        assert payload["type"] == "preview_error"
        assert payload["line"] is not None
        await ws.close()


async def test_web_validate_reports_line_and_column(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock", "Clock widget")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/login", json={"token": TOKEN})
        response = await client.post(
            "/api/boards/validate",
            json={"source": 'name = "demo"\nwidgets = [clock]', "name": "demo"},
        )
        assert response.status == 400
        payload = await response.json()
        assert payload["line"] is not None
        assert payload["column"] is not None


async def test_web_delete_active_board_stops_it(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock", "Clock widget")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/login", json={"token": TOKEN})
        pushed = await client.post("/api/push", json={"board": "demo"})
        assert pushed.status == 200
        assert (await pushed.json())["board"]["active"] is True

        deleted = await client.delete("/api/boards/demo")
        assert deleted.status == 200
        status = await (await client.get("/api/status")).json()
        assert status["board"]["active"] is False
        assert status["board"]["name"] is None
        assert await (await client.get("/api/boards")).json() == []
