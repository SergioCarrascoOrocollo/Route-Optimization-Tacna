from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REVERSE_GEOCODE_CACHE_FILE = Path(__file__).resolve().parent / "reverse_geocode_cache.json"

def db_point_to_latlon(point_text: str) -> Tuple[float, float]:
    if point_text is None:
        raise ValueError("point_text es None")
    s = point_text.strip()
    s = s.strip('()')
    parts = [p.strip() for p in s.split(',')]
    if len(parts) != 2:
        raise ValueError(f"Formato inesperado para point_text: {point_text}")
    lon = float(parts[0])
    lat = float(parts[1])
    return (lat, lon)

def latlon_to_db_point(lat: float, lon: float) -> str:
    return f"({float(lon)},{float(lat)})"

def ensure_latlon(p) -> Tuple[float, float]:
    if isinstance(p, (list, tuple)) and len(p) == 2:
        return (float(p[0]), float(p[1]))
    raise ValueError(f"Coordenadas inválidas: {p}")


def _reverse_geocode_cache_key(lat: float, lon: float, precision: int = 5) -> str:
    return f"{round(float(lat), precision):.{precision}f},{round(float(lon), precision):.{precision}f}"


def _load_reverse_geocode_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        with cache_path.open("r", encoding="utf-8") as cache_file:
            data = json.load(cache_file)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _save_reverse_geocode_cache(cache_path: Path, cache_data: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as cache_file:
        json.dump(cache_data, cache_file, ensure_ascii=False, indent=2)


def reverse_geocode(
    lat: float,
    lon: float,
    cache_path: Path | str | None = None,
    opener: Callable[..., object] | None = None,
    timeout: int = 10,
) -> str:
    cache_file = Path(cache_path) if cache_path is not None else REVERSE_GEOCODE_CACHE_FILE
    cache_data = _load_reverse_geocode_cache(cache_file)
    cache_key = _reverse_geocode_cache_key(lat, lon)

    cached_value = cache_data.get(cache_key)
    if isinstance(cached_value, str) and cached_value.strip():
        return cached_value

    request_opener = opener or urlopen
    query = urlencode(
        {
            "format": "jsonv2",
            "lat": f"{float(lat)}",
            "lon": f"{float(lon)}",
            "zoom": "18",
            "addressdetails": "1",
        }
    )
    request_url = f"https://nominatim.openstreetmap.org/reverse?{query}"
    request = Request(request_url, headers={"User-Agent": "NavExpert-Pro/1.0"})

    try:
        with request_opener(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        address = payload.get("display_name")
        if isinstance(address, str) and address.strip():
            cache_data[cache_key] = address.strip()
            _save_reverse_geocode_cache(cache_file, cache_data)
            return address.strip()
    except Exception:
        pass

    fallback = "Dirección no disponible"
    cache_data[cache_key] = fallback
    try:
        _save_reverse_geocode_cache(cache_file, cache_data)
    except OSError:
        pass
    return fallback
