# billboard_parse.py
"""Parse Billboard all.json into a deduplicated, newest-first master list."""

import json
import argparse
from pathlib import Path


def load_charts(path: Path) -> list[dict]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Expected top-level array, got {type(data).__name__}")
    return data


def extract_songs(chart: dict) -> list[tuple[str, str]]:
    """Pull (song, artist) tuples from a single chart."""
    out = []
    for entry in chart.get("data", []):
        song = (entry.get("song") or "").strip()
        artist = (entry.get("artist") or "").strip()
        if song and artist:
            out.append((song, artist))
    return out


def build_master(charts: list[dict], limit_weeks: int | None = None) -> list[dict]:
    """
    Walk charts newest-first, collecting unique (song, artist) pairs.
    Returns a list ordered newest-first.
    """
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
            master.append({
                "song": song,
                "artist": artist,
                "first_seen": chart["date"],
            })

    return master


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input", type=Path, help="Path to all.json")
    p.add_argument("-o", "--output", type=Path, default=Path("master.json"))
    p.add_argument(
        "--limit-weeks", type=int, default=None,
        help="Only process the N most recent weeks (for testing).",
    )
    args = p.parse_args()

    charts = load_charts(args.input)
    print(f"Loaded {len(charts)} charts.")

    master = build_master(charts, limit_weeks=args.limit_weeks)
    print(f"Master list: {len(master)} unique songs.")

    args.output.write_text(json.dumps(master, indent=2, ensure_ascii=False))
    print(f"Wrote {args.output}")

    # Show a preview of the newest entries
    if master:
        print("\nNewest 5 entries:")
        for item in master[:5]:
            print(f"  {item['first_seen']}  {item['song']} — {item['artist']}")


if __name__ == "__main__":
    main()
