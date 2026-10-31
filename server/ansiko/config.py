"""Defaults and the optional local TOML config."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

DEFAULT_COLS = 80
DEFAULT_ROWS = 24
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_BOARDS = "boards"
DEFAULT_WIDGETS = "widgets"
DEFAULT_CUSTOM_WIDGETS = "custom-widgets"

CONFIG_ENV = "ANSIKO_CONFIG"
CONFIG_NAME = "ansiko.local.toml"


def find_config(value: str | None = None) -> Path | None:
    if value:
        path = Path(value).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"config not found: {path}")
        return path

    env = os.environ.get(CONFIG_ENV)
    if env:
        path = Path(env).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"config not found: {path}")
        return path

    for candidate in (
        Path.cwd() / CONFIG_NAME,
        Path.home() / ".config/ansiko/config.toml",
    ):
        if candidate.is_file():
            return candidate
    return None


def load_config(value: str | None = None) -> tuple[dict, Path | None]:
    path = find_config(value)
    if path is None:
        return {}, None
    with path.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"invalid config: {path}")
    return data, path
