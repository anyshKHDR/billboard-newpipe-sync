import json
import urllib.request
from pathlib import Path

from . import config


def _fetch_or_cache(url: str, cache_path: Path, refresh: bool = False):
    """Fetch URL and cache to disk. Reuses cache unless refresh=True."""
    if cache_path.exists() and not refresh:
        print(f"  using cached {cache_path.name}")
        return json.loads(cache_path.read_text())

    print(f"  fetching {url}")
    with urllib.request.urlopen(url) as r:
        data = json.loads(r.read())

    cache_path.write_text(json.dumps(data, ensure_ascii=False))
    return data


def fetch_recent(refresh: bool = True) -> dict:
    """recent.json changes weekly — default refresh=True."""
    return _fetch_or_cache(config.RECENT_JSON_URL, config.RECENT_JSON, refresh=refresh)


def fetch_all(refresh: bool = False) -> list[dict]:
    """all.json is mostly historical — default refresh=False."""
    return _fetch_or_cache(config.ALL_JSON_URL, config.ALL_JSON, refresh=refresh)


def extract_songs(chart: dict) -> list[tuple[str, str]]:
    out = []
    for entry in chart.get("data", []):
        song   = (entry.get("song") or "").strip()
        artist = (entry.get("artist") or "").strip()
        if song and artist:
            out.append((song, artist))
    return out


def build_master(charts: list[dict], limit_weeks: int | None = None) -> list[dict]:
    """Walk charts newest-first, dedup by (song, artist), return newest-first."""
    charts_sorted = sorted(charts, key=lambda c: c["date"], reverse=True)
    if limit_weeks is not None:
        charts_sorted = charts_sorted[:limit_weeks]

    seen: set[tuple[str, str]] = set()
    master: list[dict] = []
    for chart in charts_sorted:
        for song, artist in extract_songs(chart):
            key = (song.lower(), artist.lower())
            if key in seen:
                continue
            seen.add(key)
            master.append({"song": song, "artist": artist, "first_seen": chart["date"]})
    return master
