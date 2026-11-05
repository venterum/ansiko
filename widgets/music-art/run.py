#!/usr/bin/env python3
"""Now playing album art as truecolor half-block cells."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

CACHE = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "ansiko"
    / "music-art"
)
FORMAT = "{{mpris:artUrl}}"


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def proxy() -> str:
    try:
        with Path(__file__).with_name("widget.toml").open("rb") as f:
            value = tomllib.load(f).get("proxy", "")
    except (OSError, tomllib.TOMLDecodeError):
        return ""
    return value.strip() if isinstance(value, str) else ""


def fetch(url: str) -> Path | None:
    if url.startswith("file://"):
        path = Path(urllib.parse.unquote(url[7:]))
        return path if path.is_file() else None
    if not url.startswith(("http://", "https://")):
        return None

    target = CACHE / (hashlib.sha1(url.encode()).hexdigest() + ".img")
    if not target.exists():
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(url, headers={"User-Agent": "ansiko"})
            address = proxy()
            handlers = (
                [urllib.request.ProxyHandler({"http": address, "https": address})]
                if address
                else []
            )
            opener = urllib.request.build_opener(*handlers)
            with opener.open(request, timeout=2) as response:
                target.write_bytes(response.read(4_000_000))
        except OSError:
            return None
    target.touch()
    for old in CACHE.glob("*.img"):
        if old != target and time.time() - old.stat().st_mtime > 86400:
            old.unlink(missing_ok=True)
    return target


def render_art(path: Path, cols: int, rows: int) -> list[str] | None:
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        with Image.open(path) as raw:
            image = raw.convert("RGBA")
    except OSError:
        return None

    # Album art may be transparent; flatten it on black so the phone stays readable.
    background = Image.new("RGBA", image.size, (0, 0, 0, 255))
    image = ImageOps.fit(
        Image.alpha_composite(background, image).convert("RGB"),
        (cols, rows * 2),
        Image.Resampling.LANCZOS,
    )
    pixels = image.load()
    lines = []
    for y in range(0, rows * 2, 2):
        cells = []
        for x in range(cols):
            top = pixels[x, y]
            bottom = pixels[x, y + 1]
            cells.append(
                f"\x1b[38;2;{top[0]};{top[1]};{top[2]}"
                f";48;2;{bottom[0]};{bottom[1]};{bottom[2]}m\u2580"
            )
        cells.append("\x1b[0m")
        lines.append("".join(cells))
    return lines


def triangle(step: int, size: int) -> int:
    span = 2 * size
    position = step % span
    return position if position < size else span - position


def frame(cols: int, rows: int, text: str = "") -> list[str]:
    """A box exactly the size of the art, with a bouncing ball or a message."""
    inner_w, inner_h = cols - 2, rows - 2
    if inner_w < 1 or inner_h < 1:
        return []
    text = text[:inner_w]
    step = int(time.time() * 2)
    ball_x = triangle(step, inner_w)
    ball_y = triangle(step + inner_h, inner_h)
    lines = ["\x1b[2m\u250c" + "\u2500" * inner_w + "\u2510\x1b[0m"]
    for row in range(inner_h):
        body = [" "] * inner_w
        if text and row == inner_h // 2:
            start = max((inner_w - len(text)) // 2, 0)
            body[start : start + len(text)] = text
        elif not text and row == ball_y:
            body[ball_x] = "\x1b[33m@\x1b[2m"
        lines.append("\x1b[2m\u2502\x1b[0m" + "".join(body) + "\x1b[2m\u2502\x1b[0m")
    lines.append("\x1b[2m\u2514" + "\u2500" * inner_w + "\u2518\x1b[0m")
    return lines


def parse(output: str) -> str | None:
    lines = output.splitlines()
    if not lines:
        return None
    return next((line for line in lines if line.strip()), "")


def main() -> int:
    cols = env_int("ANSIKO_COLS", 60)
    rows = env_int("ANSIKO_ROWS", 18)
    art_cols = min(cols, rows * 2)
    art_rows = art_cols // 2

    track: str | None = None
    if shutil.which("playerctl"):
        try:
            result = subprocess.run(
                ["playerctl", "metadata", "--format", FORMAT],
                capture_output=True,
                check=False,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            result = None
        track = parse(result.stdout) if result else None
    else:
        print("playerctl не установлен")
        return 1

    art = None
    if track:
        path = fetch(track)
        if path:
            art = render_art(path, art_cols, art_rows)

    if art:
        block = art
    elif track is None:
        block = frame(art_cols, art_rows, "нет трека")
    else:
        block = frame(art_cols, art_rows)

    for _ in range((rows - art_rows) // 2):
        print()
    pad = " " * ((cols - art_cols) // 2)
    for line in block:
        print(pad + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
