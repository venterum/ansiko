from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from ansiko.board import (
    Board,
    Cell,
    board_to_model,
    compose,
    create_board,
    delete_board,
    duplicate_board,
    load_board,
    parse_board_source,
    place,
    read_board_source,
    rename_board,
    source_from_model,
    summarize_board,
)
from ansiko.daemon import create_app
from ansiko.widgets import Widget, load_widget, run_widget, scan_widgets

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


def test_compose_draws_title_frame():
    cell = Cell(widget("clock", 12, 5), width=12, height=5, frame=True)
    cell.output = "12:34"
    frame = compose([cell], rows=10).decode()
    assert "┌ clock" in frame
    assert "12:34" in frame
    assert "└" in frame


def test_compose_aligns_output_in_cell():
    cell = Cell(widget("clock", 6, 3), align="center", valign="center")
    cell.output = "ab"
    frame = compose([cell], rows=10).decode()
    assert "\x1b[2;3Hab" in frame

    cell = Cell(widget("clock", 6, 3), align="right", valign="bottom")
    cell.output = "\x1b[36mab\x1b[0m"
    frame = compose([cell], rows=10).decode()
    assert "\x1b[3;5H\x1b[36mab\x1b[0m" in frame


def test_cell_alignment_roundtrip(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "clock", "printf 'clock\\n'")
    source = (
        'name = "Desk"\n'
        "[[cells]]\n"
        'widget = "clock"\n'
        "x = 0.0\ny = 0.0\nwidth = 1.0\nheight = 1.0\n"
        'align = "center"\nvalign = "bottom"\n'
    )
    spec = parse_board_source(source, "desk", widgets_dir)
    assert spec.regions is not None
    assert (spec.regions[0].align, spec.regions[0].valign) == ("center", "bottom")

    model = board_to_model(spec, "desk")
    assert model["cells"][0]["align"] == "center"
    dumped = source_from_model(model)
    assert 'align = "center"' in dumped
    assert 'valign = "bottom"' in dumped

    with pytest.raises(ValueError):
        parse_board_source(source.replace("center", "middle"), "desk", widgets_dir)


def test_explicit_fractional_cells(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "clock", "printf 'x\\n'")
    boards_dir = tmp_path / "boards"
    (boards_dir / "grid").mkdir(parents=True)
    (boards_dir / "grid" / "board.toml").write_text(
        'name = "grid"\n'
        "frame = true\n"
        "[[cells]]\n"
        'widget = "clock"\n'
        "x = 0.0\ny = 0.0\nwidth = 0.5\nheight = 1.0\n"
        "[[cells]]\n"
        'widget = "clock"\n'
        "x = 0.5\ny = 0.0\nwidth = 0.5\nheight = 0.5\n"
        "[[cells]]\n"
        'widget = "clock"\n'
        "x = 0.5\ny = 0.5\nwidth = 0.5\nheight = 0.5\n"
    )
    spec = load_board("grid", boards_dir, widgets_dir)
    assert spec.regions is not None
    assert len(spec.regions) == 3
    assert spec.regions[0].frame is True
    board = Board(
        spec.name,
        spec.widgets,
        cols=40,
        rows=20,
        emit=lambda frame: None,
        regions=spec.regions,
        frame=spec.frame,
    )
    assert [(c.x, c.y, c.width, c.height) for c in board.cells] == [
        (0, 0, 20, 20),
        (20, 0, 20, 10),
        (20, 10, 20, 10),
    ]
    board.stop()


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

    spec = load_board("demo", boards_dir, widgets_dir)
    assert spec.name == "demo"
    assert len(spec.widgets) == 1
    assert spec.regions is None

    app = create_app(TOKEN, boards_dir, widgets_dir)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/api/push", json={"board": "demo"}, headers=AUTH)
        assert response.status == 200
        board_status = (await response.json())["board"]
        assert board_status["active"] is True
        assert board_status["name"] == "demo"
        assert board_status["title"] == "demo"
        assert board_status["errors"] == []

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


def test_board_model_and_source_roundtrip(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "clock", "printf 'clock-ok\\n'")
    source = (
        'name = "Desk"\n'
        "frame = true\n"
        "[[cells]]\n"
        'widget = "clock"\n'
        "x = 0.0\ny = 0.0\nwidth = 0.5\nheight = 1.0\nframe = false\n"
        "[[cells]]\n"
        'widget = "clock"\n'
        "x = 0.5\ny = 0.0\nwidth = 0.5\nheight = 1.0\n"
    )
    spec = parse_board_source(source, "desk", widgets_dir)
    model = board_to_model(spec, "desk")
    assert model["mode"] == "cells"
    assert model["name"] == "Desk"
    assert model["cells"][0]["frame_override"] is False
    assert model["cells"][1]["frame_override"] is None
    dumped = source_from_model(model)
    spec2 = parse_board_source(dumped, "desk", widgets_dir)
    assert spec2.name == "Desk"
    assert spec2.regions is not None
    assert spec2.regions[0].frame is False
    assert spec2.regions[1].frame is True


def test_create_duplicate_rename_delete_board(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "clock", "printf 'clock\\n'")
    write_widget(widgets_dir / "calendar", "printf 'calendar\\n'")
    boards_dir = tmp_path / "boards"

    create_board(
        "new",
        boards_dir,
        widgets_dir,
        template="columns",
        widget_names=["clock", "calendar"],
        frame=True,
    )
    source = read_board_source("new", boards_dir)
    assert "[[cells]]" in source
    assert 'widget = "clock"' in source
    assert "frame = false" not in source
    summary = summarize_board("new", boards_dir, widgets_dir)
    assert summary["valid"] is True
    assert summary["mode"] == "cells"
    assert summary["widget_count"] == 2

    duplicate_board("new", "copy", boards_dir, widgets_dir)
    assert summarize_board("copy", boards_dir, widgets_dir)["valid"] is True
    rename_board("copy", "renamed", boards_dir)
    assert summarize_board("renamed", boards_dir, widgets_dir)["valid"] is True
    delete_board("renamed", boards_dir)
    assert not (boards_dir / "renamed" / "board.toml").exists()


def test_create_board_requires_widgets(tmp_path):
    boards_dir = tmp_path / "boards"
    try:
        create_board("empty", boards_dir, tmp_path / "widgets")
    except ValueError as exc:
        assert "no widgets" in str(exc)
    else:
        raise AssertionError("create_board should reject an empty widget set")


def test_scan_widgets_reports_bad_manifest(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "clock", "printf 'ok\\n'")
    bad = widgets_dir / "bad"
    bad.mkdir()
    (bad / "widget.toml").write_text('name = "bad"\n')
    widgets, errors = scan_widgets(widgets_dir)
    assert [widget.id for widget in widgets] == ["clock"]
    assert errors and errors[0]["id"] == "bad"


async def test_board_reports_widget_errors(tmp_path):
    widgets_dir = tmp_path / "widgets"
    write_widget(widgets_dir / "bad", "echo boom >&2\nexit 2\n", interval=0.1)
    frames: list[bytes] = []
    board = Board(
        "demo",
        [load_widget(widgets_dir / "bad")],
        cols=40,
        rows=10,
        emit=frames.append,
    )
    board.start()
    try:
        for _ in range(60):
            if board.errors():
                break
            await asyncio.sleep(0.02)
    finally:
        board.stop()
    assert board.errors()
    assert board.errors()[0]["widget"] == "bad"


def test_custom_widgets_override_bundled(tmp_path):
    bundled = tmp_path / "widgets"
    custom = tmp_path / "custom-widgets"
    write_widget(bundled / "clock", "printf 'bundled\\n'")
    write_widget(custom / "clock", "printf 'custom\\n'")
    write_widget(custom / "weather", "printf 'sunny\\n'")

    widgets, errors = scan_widgets(bundled, custom)
    assert errors == []
    by_id = {widget.id: widget for widget in widgets}
    assert by_id["clock"].source == "custom"
    assert by_id["clock"].directory == custom / "clock"
    assert by_id["weather"].source == "custom"

    spec = parse_board_source(
        'name = "demo"\nwidgets = ["clock"]\n',
        "demo",
        bundled,
        custom,
    )
    assert spec.widgets[0].directory == custom / "clock"
