"""Widget manifests and script execution."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path

MANIFEST = "widget.toml"


@dataclass(frozen=True)
class Widget:
    name: str
    command: str
    interval: float
    width: int
    height: int
    timeout: float
    directory: Path


def _text(data: dict, key: str, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"widget: {key!r} must be a non-empty string")
    return value.strip()


def _number(data: dict, key: str, default: float, minimum: float) -> float:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"widget: {key!r} must be a number")
    if value < minimum:
        raise ValueError(f"widget: {key!r} must be >= {minimum:g}")
    return float(value)


def _integer(data: dict, key: str, default: int, minimum: int) -> int:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"widget: {key!r} must be an integer")
    if value < minimum:
        raise ValueError(f"widget: {key!r} must be >= {minimum}")
    return value


def load_widget(directory: Path) -> Widget:
    manifest = directory / MANIFEST
    if not manifest.is_file():
        raise FileNotFoundError(f"missing {manifest}")
    with manifest.open("rb") as f:
        data = tomllib.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"invalid manifest: {manifest}")

    return Widget(
        name=_text(data, "name", directory.name),
        command=_text(data, "command"),
        interval=_number(data, "interval", 1.0, 0.1),
        width=_integer(data, "width", 20, 1),
        height=_integer(data, "height", 5, 1),
        timeout=_number(data, "timeout", 5.0, 0.1),
        directory=directory,
    )


def _argv(widget: Widget) -> list[str]:
    parts = shlex.split(widget.command)
    if not parts:
        raise ValueError("widget: empty command")
    first = parts[0]
    if "/" in first or first.startswith("."):
        path = (widget.directory / first).resolve()
        if not path.exists():
            raise FileNotFoundError(f"command not found: {path}")
        parts[0] = str(path)
    elif shutil.which(first) is None:
        local = widget.directory / first
        if local.exists():
            parts[0] = str(local)
    return parts


async def run_widget(widget: Widget) -> tuple[str, str | None]:
    """Run one widget once. Returns (stdout, error); never raises for script failures."""
    try:
        argv = _argv(widget)
    except (OSError, ValueError) as e:
        return "", str(e)

    env = os.environ.copy()
    env["ANSIKO_COLS"] = str(widget.width)
    env["ANSIKO_ROWS"] = str(widget.height)

    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(widget.directory),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as e:
        return "", f"cannot start: {e.strerror or e}"

    try:
        out, err = await asyncio.wait_for(proc.communicate(), widget.timeout)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return "", f"timeout after {widget.timeout:g}s"
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise

    if proc.returncode:
        detail = err.decode("utf-8", "replace").strip() or f"exit {proc.returncode}"
        return "", f"exit {proc.returncode}: {detail}"

    output = out.decode("utf-8", "replace").replace("\r\n", "\n").rstrip("\n")
    return output, None
