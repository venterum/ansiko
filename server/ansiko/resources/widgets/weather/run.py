#!/usr/bin/env python3
"""Current weather from Open-Meteo, with a small offline cache.

The location is read from this widget's own manifest, so no API key or
per-user code edit is needed:

    latitude  = 59.9343
    longitude = 30.3351
    city      = "САНКТ-ПЕТЕРБУРГ"
    timezone  = "Europe/Moscow"

Open-Meteo does not require a key. A failed request falls back to the last
successful response for 24 hours, then to a short "нет данных" line.
"""

from __future__ import annotations

import json
import os
import re
import time
import tomllib
import urllib.parse
import urllib.request
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
MANIFEST = Path(__file__).with_name("widget.toml")
CACHE = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    / "ansiko"
    / "weather.json"
)
CACHE_MAX_AGE = 24 * 60 * 60
CACHE_FRESH_AGE = 10 * 60

DESCRIPTIONS = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "слабая морось",
    53: "морось",
    55: "сильная морось",
    56: "ледяная морось",
    57: "сильная ледяная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "ледяной дождь",
    67: "сильный ледяной дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "небольшие ливни",
    81: "ливни",
    82: "сильные ливни",
    85: "снежные ливни",
    86: "сильные снежные ливни",
    95: "гроза",
    96: "гроза с градом",
    99: "сильная гроза с градом",
}


def env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, default)))
    except ValueError:
        return default


def width(text: str) -> int:
    return len(ANSI.sub("", text))


def location() -> tuple[float, float, str, str]:
    try:
        with MANIFEST.open("rb") as f:
            data = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        data = {}
    try:
        latitude = float(data.get("latitude", 59.9343))
        longitude = float(data.get("longitude", 30.3351))
    except (TypeError, ValueError):
        latitude, longitude = 59.9343, 30.3351
    city = data.get("city", "САНКТ-ПЕТЕРБУРГ")
    timezone = data.get("timezone", "Europe/Moscow")
    return (
        latitude,
        longitude,
        city if isinstance(city, str) and city.strip() else "САНКТ-ПЕТЕРБУРГ",
        timezone if isinstance(timezone, str) and timezone.strip() else "Europe/Moscow",
    )


def fetch(latitude: float, longitude: float, timezone: str) -> dict | None:
    query = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:g}",
            "longitude": f"{longitude:g}",
            "current": "temperature_2m,weather_code,wind_speed_10m",
            "timezone": timezone,
        }
    )
    request = urllib.request.Request(
        f"https://api.open-meteo.com/v1/forecast?{query}",
        headers={"User-Agent": "ansiko-weather/0.2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            payload = json.load(response)
        current = payload["current"]
        return {
            "temperature": float(current["temperature_2m"]),
            "code": int(current["weather_code"]),
            "wind": float(current["wind_speed_10m"]),
            "saved": time.time(),
        }
    except (OSError, KeyError, TypeError, ValueError):
        return None


def cached() -> dict | None:
    try:
        payload = json.loads(CACHE.read_text(encoding="utf-8"))
        saved = float(payload.get("saved", 0))
        if time.time() - saved > CACHE_MAX_AGE:
            return None
        float(payload["temperature"])
        int(payload["code"])
        float(payload["wind"])
        return payload
    except (OSError, KeyError, TypeError, ValueError):
        return None


def save_cache(data: dict) -> None:
    try:
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        CACHE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def current_weather() -> tuple[dict | None, bool]:
    cached_data = cached()
    if (
        cached_data is not None
        and time.time() - float(cached_data["saved"]) < CACHE_FRESH_AGE
    ):
        return cached_data, False
    latitude, longitude, _, timezone = location()
    data = fetch(latitude, longitude, timezone)
    if data is not None:
        save_cache(data)
        return data, False
    return cached_data, cached_data is not None


def main() -> int:
    cols = env_int("ANSIKO_COLS", 30)
    rows = env_int("ANSIKO_ROWS", 10)
    _, _, city, _ = location()
    data, stale = current_weather()
    if data is None:
        print("нет данных о погоде".center(cols))
        return 0

    temperature = round(float(data["temperature"]))
    wind = round(float(data["wind"]))
    description = DESCRIPTIONS.get(int(data["code"]), "неизвестно")
    freshness = " · кеш" if stale else ""
    lines = [
        f"\x1b[1;36m{city}\x1b[0m",
        "",
        f"\x1b[1;33m{temperature:+d}°C\x1b[0m  {description}",
        f"\x1b[2mветер {wind} км/ч{freshness}\x1b[0m",
    ]
    top = max((rows - len(lines)) // 2, 0)
    for _ in range(top):
        print()
    for line in lines:
        print(" " * max((cols - width(line)) // 2, 0) + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
