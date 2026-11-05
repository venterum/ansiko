from __future__ import annotations

from pathlib import Path

import pytest

from ansiko.board import list_board_summaries
from ansiko.config import default_dir
from ansiko.widgets import scan_widgets

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parents[1] / "ansiko" / "resources"


def files(root: Path) -> set[Path]:
    return {
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


@pytest.mark.parametrize("name", ["boards", "widgets"])
def test_package_resources_match_checkout(name: str) -> None:
    source = ROOT / name
    packaged = PACKAGE / name
    if not source.is_dir():
        pytest.skip("running outside a source checkout")
    assert packaged.is_dir(), f"run scripts/sync_bundled.py ({packaged} missing)"
    assert files(source) == files(packaged)
    for relative in sorted(files(source)):
        assert (source / relative).read_bytes() == (packaged / relative).read_bytes(), (
            relative
        )


def test_all_bundled_boards_and_widgets_are_valid() -> None:
    boards = default_dir("boards")
    widgets = default_dir("widgets")
    summaries = list_board_summaries(boards, widgets)
    assert summaries
    broken = [
        {"name": item["name"], "error": item["error"]}
        for item in summaries
        if not item["valid"]
    ]
    assert broken == []

    catalog, errors = scan_widgets(widgets)
    assert catalog
    assert errors == []
