"""Widget manifests and script execution."""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import shutil
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

MANIFEST = "widget.toml"
SETTING_TYPES = ("select", "range", "number", "text", "toggle")
RESERVED_SETTING_KEYS = {
    "name",
    "description",
    "command",
    "interval",
    "width",
    "height",
    "timeout",
    "settings",
}
SETTING_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class WidgetSetting:
    key: str
    type: str
    label: str
    default: object
    value: object
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[str, ...] = ()
    help: str = ""

    def validate(self, value: object) -> object:
        return _setting_value(
            self.type,
            value,
            self.options,
            self.minimum,
            self.maximum,
            f"widget setting {self.key!r}",
        )

    def to_dict(self) -> dict:
        data = {
            "key": self.key,
            "type": self.type,
            "label": self.label,
            "default": self.default,
            "value": self.value,
            "help": self.help,
        }
        if self.minimum is not None:
            data["min"] = self.minimum
        if self.maximum is not None:
            data["max"] = self.maximum
        if self.step is not None:
            data["step"] = self.step
        if self.options:
            data["options"] = list(self.options)
        return data


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
    settings: tuple[WidgetSetting, ...] = ()

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
            "settings": [setting.to_dict() for setting in self.settings],
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


def _setting_text(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"widget setting: {key!r} must be a string")
    return value.strip()


def _optional_number(data: dict, key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"widget setting: {key!r} must be a number")
    return float(value)


def _setting_value(
    kind: str,
    value: object,
    options: tuple[str, ...],
    minimum: float | None,
    maximum: float | None,
    where: str,
) -> object:
    if kind == "select":
        if not isinstance(value, str) or value not in options:
            raise ValueError(f"{where} must be one of {options}")
        return value
    if kind == "text":
        if not isinstance(value, str):
            raise TypeError(f"{where} must be a string")
        return value
    if kind == "toggle":
        if not isinstance(value, bool):
            raise TypeError(f"{where} must be a boolean")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{where} must be a number")
    number = float(value)
    if minimum is not None and number < minimum:
        raise ValueError(f"{where} must be >= {minimum:g}")
    if maximum is not None and number > maximum:
        raise ValueError(f"{where} must be <= {maximum:g}")
    return number


def _parse_settings(data: dict) -> tuple[WidgetSetting, ...]:
    raw = data.get("settings", [])
    if not isinstance(raw, list):
        raise TypeError("widget: 'settings' must be an array of tables")
    settings: list[WidgetSetting] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("widget: each setting must be a table")
        key = _text(item, "key")
        if not SETTING_KEY.fullmatch(key):
            raise ValueError(
                "widget setting: 'key' must contain only letters, digits, '-' and '_'"
            )
        if key in RESERVED_SETTING_KEYS:
            raise ValueError(f"widget setting: {key!r} is reserved")
        if key in seen:
            raise ValueError(f"widget setting: duplicate key {key!r}")
        seen.add(key)
        kind = _text(item, "type")
        if kind not in SETTING_TYPES:
            raise ValueError(
                f"widget setting {key!r}: 'type' must be one of {SETTING_TYPES}"
            )
        minimum = _optional_number(item, "min")
        maximum = _optional_number(item, "max")
        step = _optional_number(item, "step")
        if step is not None and step <= 0:
            raise ValueError(f"widget setting {key!r}: 'step' must be positive")
        options: tuple[str, ...] = ()
        if kind == "select":
            raw_options = item.get("options")
            if not isinstance(raw_options, list) or not raw_options:
                raise ValueError(
                    f"widget setting {key!r}: 'options' must be a non-empty list"
                )
            option_list: list[str] = []
            for option in raw_options:
                if not isinstance(option, str) or not option.strip():
                    raise TypeError(
                        f"widget setting {key!r}: options must be non-empty strings"
                    )
                option_list.append(option)
            options = tuple(option_list)
        if kind == "range":
            if minimum is None or maximum is None:
                raise ValueError(
                    f"widget setting {key!r}: range requires 'min' and 'max'"
                )
            if maximum <= minimum:
                raise ValueError(
                    f"widget setting {key!r}: 'max' must be greater than 'min'"
                )
            if step is None:
                step = 0.1
        elif kind == "number" and step is None:
            step = 1.0
        if "default" not in item:
            raise ValueError(f"widget setting {key!r}: missing 'default'")
        default = _setting_value(
            kind,
            item["default"],
            options,
            minimum,
            maximum,
            f"widget setting {key!r}: default",
        )
        try:
            value = _setting_value(
                kind,
                data.get(key, default),
                options,
                minimum,
                maximum,
                f"widget setting {key!r}: value",
            )
        except (TypeError, ValueError):
            value = default
        settings.append(
            WidgetSetting(
                key=key,
                type=kind,
                label=_setting_text(item, "label", key) or key,
                default=default,
                value=value,
                minimum=minimum,
                maximum=maximum,
                step=step,
                options=options,
                help=_setting_text(item, "help"),
            )
        )
    return tuple(settings)


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
        settings=_parse_settings(data),
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


def save_widget_settings(
    widget: Widget,
    values: dict,
    custom_widgets_dir: Path | None = None,
) -> Widget:
    """Validate and persist editable settings, copying bundled widgets locally."""
    if not widget.settings:
        raise ValueError(f"widget {widget.id!r} has no editable settings")
    if not isinstance(values, dict):
        raise TypeError("settings must be an object")
    known = {setting.key: setting for setting in widget.settings}
    clean: dict[str, object] = {}
    for key, value in values.items():
        if not isinstance(key, str) or key not in known:
            raise ValueError(f"unknown widget setting: {key!r}")
        clean[key] = known[key].validate(value)

    target = widget
    if widget.source != "custom":
        if custom_widgets_dir is None:
            raise ValueError("custom widgets directory is not configured")
        target_dir = custom_widgets_dir / widget.id
        if target_dir.exists():
            raise FileExistsError(f"custom widget already exists: {target_dir}")
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            widget.directory,
            target_dir,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        target = load_widget(target_dir, source="custom")

    path = target.directory / MANIFEST
    text = path.read_text(encoding="utf-8")
    for key, value in clean.items():
        text = _set_toml_value(text, key, value)
    _write_atomic(path, text)
    return load_widget(target.directory, source=target.source)


def _toml_literal(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:g}"
    if isinstance(value, str):
        return _toml_string(value)
    raise TypeError(f"unsupported setting value: {value!r}")


def _toml_string(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _split_comment(value: str) -> tuple[str, str]:
    in_string = False
    escaped = False
    quote = ""
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if in_string:
            if char == "\\":
                escaped = True
            elif char == quote:
                in_string = False
        elif char in ('"', "'"):
            in_string = True
            quote = char
        elif char == "#":
            return value[:index], value[index:]
    return value, ""


def _set_toml_value(text: str, key: str, value: object) -> str:
    literal = _toml_literal(value)
    lines = text.splitlines()
    header = next(
        (index for index, line in enumerate(lines) if line.lstrip().startswith("[")),
        len(lines),
    )
    pattern = re.compile(rf"^(\s*{re.escape(key)}\s*=\s*)(.*)$")
    for index in range(header):
        match = pattern.match(lines[index])
        if match is None:
            continue
        raw = match.group(2)
        if raw.lstrip().startswith(("[", "{", '"""', "'''")):
            raise ValueError(
                f"widget setting {key!r}: only scalar values can be edited from the web"
            )
        before_comment, comment = _split_comment(raw)
        trailing = before_comment[len(before_comment.rstrip()) :]
        lines[index] = f"{match.group(1)}{literal}{trailing}{comment}"
        return "\n".join(lines) + "\n"
    new_line = f"{key} = {literal}"
    if header == len(lines):
        lines.append(new_line)
    else:
        lines.insert(header, new_line)
    return "\n".join(lines) + "\n"


def _write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", text=True)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


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
