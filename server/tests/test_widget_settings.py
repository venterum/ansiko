from __future__ import annotations

from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ansiko.daemon import create_app
from ansiko.widgets import load_widget, save_widget_settings

TOKEN = "test-token"
SCHEMA = """
[[settings]]
key = "style"
type = "select"
label = "Style"
options = ["blocks", "ascii"]
default = "blocks"

[[settings]]
key = "gamma"
type = "range"
label = "Gamma"
min = 0.1
max = 2.0
step = 0.05
default = 1.0

[[settings]]
key = "enabled"
type = "toggle"
label = "Enabled"
default = true

[[settings]]
key = "caption"
type = "text"
label = "Caption"
default = "hello"
"""


def write_widget(directory: Path) -> Path:
    directory.mkdir(parents=True)
    (directory / "widget.toml").write_text(
        f'name = "{directory.name}"\n'
        'command = "./run.sh"\n'
        'style = "blocks"   # keep me\n' + SCHEMA
    )
    return directory


def test_load_widget_settings(tmp_path):
    directory = write_widget(tmp_path / "demo")
    path = directory / "widget.toml"
    text = path.read_text().replace('style = "blocks"', 'style = "ascii"')
    path.write_text(text.replace("\n[[settings]]", "\ngamma = 1.5\n\n[[settings]]", 1))
    widget = load_widget(directory)
    values = {item["key"]: item["value"] for item in widget.to_dict()["settings"]}
    assert values == {
        "style": "ascii",
        "gamma": 1.5,
        "enabled": True,
        "caption": "hello",
    }


def test_save_widget_settings_preserves_comments_and_adds_keys(tmp_path):
    directory = write_widget(tmp_path / "custom" / "demo")
    widget = load_widget(directory, source="custom")
    updated = save_widget_settings(
        widget,
        {"style": "ascii", "gamma": 0.5, "enabled": False, "caption": 'a "b" # c'},
    )
    text = (directory / "widget.toml").read_text()
    assert 'style = "ascii"   # keep me' in text
    assert text.index("gamma = 0.5") < text.index("[[settings]]")
    assert "enabled = false" in text
    assert 'caption = "a \\"b\\" # c"' in text
    values = {item["key"]: item["value"] for item in updated.to_dict()["settings"]}
    assert values == {
        "style": "ascii",
        "gamma": 0.5,
        "enabled": False,
        "caption": 'a "b" # c',
    }


def test_save_widget_settings_copies_bundled(tmp_path):
    bundled = write_widget(tmp_path / "widgets" / "demo")
    custom = tmp_path / "custom-widgets"
    widget = load_widget(bundled, source="bundled")
    updated = save_widget_settings(widget, {"style": "ascii"}, custom)
    assert updated.source == "custom"
    assert updated.settings[0].value == "ascii"
    assert (custom / "demo" / "widget.toml").is_file()
    assert 'style = "ascii"' in (custom / "demo" / "widget.toml").read_text()
    assert 'style = "blocks"' in (bundled / "widget.toml").read_text()


def test_save_widget_settings_validates_before_copying(tmp_path):
    bundled = write_widget(tmp_path / "widgets" / "demo")
    custom = tmp_path / "custom-widgets"
    widget = load_widget(bundled, source="bundled")
    with pytest.raises(ValueError):
        save_widget_settings(widget, {"style": "nope"}, custom)
    with pytest.raises(ValueError):
        save_widget_settings(widget, {"missing": 1}, custom)
    assert not (custom / "demo").exists()


async def test_web_widget_settings(tmp_path):
    widgets = tmp_path / "widgets"
    custom = tmp_path / "custom-widgets"
    boards = tmp_path / "boards"
    write_widget(widgets / "demo")
    app = create_app(TOKEN, boards, widgets, custom)
    async with TestClient(TestServer(app)) as client:
        await client.post("/api/login", json={"token": TOKEN})
        response = await client.post(
            "/api/widgets/demo/settings",
            json={"settings": {"style": "ascii", "gamma": 0.25}},
        )
        assert response.status == 200
        payload = await response.json()
        assert payload["widget"]["source"] == "custom"
        assert (custom / "demo" / "widget.toml").is_file()
        data = await (await client.get("/api/widgets")).json()
        widget = next(item for item in data["widgets"] if item["id"] == "demo")
        values = {item["key"]: item["value"] for item in widget["settings"]}
        assert values["style"] == "ascii"
        assert values["gamma"] == 0.25

        bad = await client.post(
            "/api/widgets/demo/settings", json={"settings": {"style": "nope"}}
        )
        assert bad.status == 400
        missing = await client.post(
            "/api/widgets/missing/settings", json={"settings": {}}
        )
        assert missing.status == 404
