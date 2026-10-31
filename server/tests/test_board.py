from __future__ import annotations

import asyncio
from pathlib import Path

from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from ansiko.board import Board, Cell, compose, load_board, place
from ansiko.daemon import create_app
from ansiko.widgets import Widget, load_widget, run_widget

TOKEN = "test-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def widget(name: str, width: int = 20, height: int = 3) -> Widget:
    return Widget(
        name=name,
        command="./run.sh",
        interval=1.0,
        width=width,
        height=height,
        timeout=1.0,
        directory=Path("/tmp") / name,
    )


def write_widget(
    directory: Path,
    body: str,
    *,
    interval: float = 0.1,
    timeout: float = 1.0,
    width: int = 20,
    height: int = 3,
) -> Path:
    directory.mkdir(parents=True)
    script = directory / "run.sh"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)
    (directory / "widget.toml").write_text(
        f"name = {directory.name!r}\n"
        'command = "./run.sh"\n'
        f"interval = {interval}\n"
        f"width = {width}\n"
        f"height = {height}\n"
        f"timeout = {timeout}\n"
    )
    return directory


def test_layout_wraps_and_clips():
    cells = [Cell(widget("one", 20, 3)), Cell(widget("two", 24, 4))]
    place(cells, cols=50, rows=20)
    assert (cells[0].x, cells[0].y) == (0, 0)
    assert (cells[1].x, cells[1].y) == (21, 0)

    place(cells, cols=40, rows=20)
    assert (cells[0].x, cells[0].y) == (0, 0)
    assert (cells[1].x, cells[1].y) == (0, 4)

    place(cells, cols=40, rows=3)
    assert cells[1].x == -1 and cells[1].y == -1


def test_compose_contains_output_and_error_cell():
    cells = [Cell(widget("clock", 10, 2)), Cell(widget("bad", 30, 2))]
    cells[0].output = "12:34"
    cells[1].error = "exit 3: boom"
    frame = compose(cells, rows=10).decode()
    assert "12:34" in frame
    assert "! bad: exit 3: boom" in frame
    assert "\x1b[1;1H" in frame


def test_compose_clips_to_cell_width():
    cell = Cell(widget("clock", 5, 2))
    cell.output = "abcdef"
    frame = compose([cell], rows=10).decode()
    assert "abcde" in frame
    assert "abcdef" not in frame


async def test_run_widget_success_timeout_and_failure(tmp_path):
    ok = write_widget(tmp_path / "ok", "printf 'hello\\n'")
    output, error = await run_widget(load_widget(ok))
    assert output == "hello"
    assert error is None

    slow = write_widget(tmp_path / "slow", "sleep 1\n", timeout=0.1)
    output, error = await run_widget(load_widget(slow))
    assert output == ""
    assert error is not None and "timeout" in error

    bad = write_widget(tmp_path / "bad", "echo boom >&2\nexit 3\n")
    output, error = await run_widget(load_widget(bad))
    assert output == ""
    assert error is not None and "exit 3" in error and "boom" in error


async def test_board_runs_widgets_and_emits_frames(tmp_path):
    widgets_dir = tmp_path / "widgets"
    first = write_widget(widgets_dir / "one", "printf 'one-ok\\n'")
    second = write_widget(widgets_dir / "two", "printf 'two-ok\\n'")

    frames: list[bytes] = []
    board = Board(
        "demo",
        [load_widget(first), load_widget(second)],
        cols=40,
        rows=10,
        emit=frames.append,
    )
    board.start()
    try:
        for _ in range(50):
            if any(b"one-ok" in frame and b"two-ok" in frame for frame in frames):
                break
            await asyncio.sleep(0.02)
    finally:
        board.stop()

    assert any(b"one-ok" in frame and b"two-ok" in frame for frame in frames)


async def test_load_board_and_push_endpoint(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "clock", "printf 'pushed-ok\\n'")
    boards_dir = tmp_path / "boards"
    (boards_dir / "demo").mkdir(parents=True)
    (boards_dir / "demo" / "board.toml").write_text(
        'name = "demo"\nwidgets = ["clock"]\n'
    )

    title, widgets = load_board("demo", boards_dir, widgets_dir)
    assert title == "demo"
    assert len(widgets) == 1

    app = create_app(TOKEN, boards_dir, widgets_dir)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/push", json={"board": "demo"}, headers=AUTH)
        assert response.status == 200
        assert (await response.json())["board"] == {"active": True, "name": "demo"}

        ws = await client.ws_connect("/ws/display")
        await ws.send_json({"type": "hello", "token": TOKEN, "cols": 40, "rows": 10})
        assert (await ws.receive()).type == WSMsgType.TEXT

        frame = b""
        for _ in range(50):
            message = await asyncio.wait_for(ws.receive(), 1)
            if message.type == WSMsgType.BINARY:
                frame += message.data
            if b"pushed-ok" in frame:
                break
        assert b"pushed-ok" in frame
        await ws.close()
