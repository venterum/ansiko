from __future__ import annotations

from pathlib import Path

from aiohttp.test_utils import TestClient, TestServer

from ansiko.daemon import create_app

TOKEN = "test-token"


def write_widget(directory: Path) -> None:
    directory.mkdir(parents=True)
    script = directory / "run.sh"
    script.write_text("#!/bin/sh\nprintf 'web-ok\\n'\n")
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


async def test_web_login_boards_save_pair_and_push(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        page = await client.get("/")
        assert page.status == 200
        assert "Pair phone" in await page.text()

        assert (await client.get("/api/boards")).status == 401
        assert (await client.get("/api/pair")).status == 401

        wrong = await client.post("/api/login", json={"token": "wrong"})
        assert wrong.status == 401

        login = await client.post("/api/login", json={"token": TOKEN})
        assert login.status == 200

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

        created = await client.post("/api/boards", json={"name": "second"})
        assert created.status == 201
        assert "second" in await (await client.get("/api/boards")).json()

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


async def test_web_rejects_invalid_board_source(tmp_path):
    widgets = tmp_path / "widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "clock")
    write_board(boards / "demo")

    app = create_app(TOKEN, boards, widgets)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/login", json={"token": TOKEN})
        bad = await client.put(
            "/api/boards/demo",
            data='name = "demo"\nwidgets = ["missing"]\n',
        )
        assert bad.status in (400, 404)
