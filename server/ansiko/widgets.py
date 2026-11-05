"""Widget manifests and script execution."""

from __future__ import annotations

import asyncio
import os
import shlex
import shutil
import sys
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
    description: str = ""
    source: str = "bundled"

    @property
    def id(self) -> str:
        """The directory name used by boards and the web UI."""
        return self.directory.name

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "command": self.command,
            "interval": self.interval,
            "width": self.width,
            "height": self.height,
            "timeout": self.timeout,
            "path": str(self.directory),
            "source": self.source,
        }


def _text(data: dict, key: str, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"widget: {key!r} must be a non-empty string")
    return value.strip()


def _description(data: dict) -> str:
    value = data.get("description", "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError("widget: 'description' must be a string")
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


def load_widget(directory: Path, source: str = "bundled") -> Widget:
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
        description=_description(data),
        source=source,
    )


def scan_widgets(
    directory: Path, custom_dir: Path | None = None
) -> tuple[list[Widget], list[dict]]:
    """Load widgets from custom and bundled directories.

    The custom directory is searched first. If a custom widget has an invalid
    manifest, its error is reported instead of silently falling back to the
    bundled widget with the same id.
    """
    widgets: list[Widget] = []
    errors: list[dict] = []
    seen: set[str] = set()
    roots: list[tuple[Path, str]] = []
    if custom_dir is not None:
        roots.append((custom_dir, "custom"))
    roots.append((directory, "bundled"))
    for root, source in roots:
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if child.name in seen:
                continue
            if not child.is_dir() or child.name.startswith("."):
                continue
            if not (child / MANIFEST).is_file():
                continue
            seen.add(child.name)
            try:
                widgets.append(load_widget(child, source=source))
            except (OSError, TypeError, ValueError) as e:
                errors.append(
                    {
                        "id": child.name,
                        "source": source,
                        "path": str(child),
                        "error": str(e),
                    }
                )
    return widgets, errors


def resolve_widget(
    name: str, directory: Path, custom_dir: Path | None = None
) -> Widget:
    """Resolve a widget id, preferring the custom directory."""
    roots: list[tuple[Path, str]] = []
    if custom_dir is not None:
        roots.append((custom_dir, "custom"))
    roots.append((directory, "bundled"))
    for root, source in roots:
        candidate = root / name
        if (candidate / MANIFEST).is_file():
            return load_widget(candidate, source=source)
    raise FileNotFoundError(f"widget not found: {name}")


def _argv(widget: Widget) -> list[str]:
    parts = shlex.split(widget.command)
    if not parts:
        raise ValueError("widget: empty command")
    first = parts[0]
    if "/" in first or first.startswith("."):
        path = (widget.directory / first).resolve()
        if not path.exists():
            raise FileNotFoundError(f"command not found: {path}")
        if path.suffix == ".py" and not os.access(path, os.X_OK):
            # Wheels do not reliably preserve executable bits on data files.
            parts = [sys.executable, str(path), *parts[1:]]
        else:
            parts[0] = str(path)
    elif shutil.which(first) is None:
        local = widget.directory / first
        if local.exists():
            parts[0] = str(local)
    return parts


async def run_widget(
    widget: Widget, cols: int | None = None, rows: int | None = None
) -> tuple[str, str | None]:
    """Run one widget once. Returns (stdout, error); never raises for script failures."""
    try:
        argv = _argv(widget)
    except (OSError, ValueError) as e:
        return "", str(e)

    env = os.environ.copy()
    env["ANSIKO_COLS"] = str(widget.width if cols is None else cols)
    env["ANSIKO_ROWS"] = str(widget.height if rows is None else rows)

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
