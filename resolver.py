# resolver.py
"""
Resolve Billboard songs to YouTube video IDs via ytmusicapi.
Resumable: progress is checkpointed to urls.json and failed.json on every song.
"""

import json
import time
import argparse
import unicodedata
from pathlib import Path

from ytmusicapi import YTMusic


# ---------- helpers ----------

def strip_diacritics(s: str) -> str:
    """Normalize 'ADÉLA' -> 'adela', 'Beyoncé' -> 'beyonce', etc."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )


def artist_matches(billboard_artist: str, yt_artists: list[dict]) -> bool:
    """Case- and diacritic-insensitive substring match, bidirectional."""
    bb = strip_diacritics(billboard_artist.lower())
    if not bb:
        return False
    for a in yt_artists:
        name = strip_diacritics((a.get("name") or "").lower())
        if not name:
            continue
        if bb in name or name in bb:
            return True
    return False


def song_key(entry: dict) -> str:
    return f"{entry['song'].lower()}||{entry['artist'].lower()}"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def save_json(path: Path, data):
    """Atomic write via .tmp + rename, so a crash never corrupts the cache."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    tmp.replace(path)


# ---------- core ----------

def resolve_one(yt: YTMusic, entry: dict) -> tuple[dict | None, str | None]:
    """Returns (resolved_dict, None) on success, or (None, reason) on failure."""
    query = f"{entry['song']} {entry['artist']}"
    try:
        results = yt.search(query, filter="songs")
    except Exception as e:
        return None, f"api_error: {e}"

    if not results:
        return None, "no_results"

    top = results[0]
    video_id = top.get("videoId")
    if not video_id:
        return None, "no_video_id"

    if not artist_matches(entry["artist"], top.get("artists") or []):
        got = [a.get("name") for a in (top.get("artists") or [])]
        return None, f"artist_mismatch: got {got}"

    return {
        "song": entry["song"],
        "artist": entry["artist"],
        "first_seen": entry["first_seen"],
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "yt_title": top.get("title"),
        "yt_duration": top.get("duration_seconds"),
    }, None


# ---------- main ----------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("master", type=Path, help="Path to master.json")
    p.add_argument("--urls", type=Path, default=Path("urls.json"))
    p.add_argument("--failed", type=Path, default=Path("failed.json"))
    p.add_argument("--since", type=str, default=None,
                   help="Only process songs with first_seen >= YYYY-MM-DD")
    p.add_argument("--limit", type=int, default=None,
                   help="Stop after N songs (for testing).")
    p.add_argument("--sleep", type=float, default=1.5,
                   help="Seconds between searches (default 1.5).")
    args = p.parse_args()

    master = load_json(args.master, [])
    resolved = load_json(args.urls, [])
    failed = load_json(args.failed, [])

    done_keys = {song_key(r) for r in resolved}
    failed_keys = {song_key(f) for f in failed}

    todo = []
    for entry in master:
        if args.since and entry["first_seen"] < args.since:
            continue
        k = song_key(entry)
        if k in done_keys or k in failed_keys:
            continue
        todo.append(entry)

    if args.limit:
        todo = todo[:args.limit]

    print(f"Master entries:          {len(master)}")
    print(f"Already resolved:        {len(resolved)}")
    print(f"Previously failed:       {len(failed)}")
    print(f"To process this run:     {len(todo)}")
    if todo:
        est_min = len(todo) * (args.sleep + 0.4) / 60
        print(f"Estimated time:          ~{est_min:.0f} min")
    print()

    if not todo:
        print("Nothing to do.")
        return

    yt = YTMusic()  # unauthenticated — fine on residential IP

    for i, entry in enumerate(todo, 1):
        result, reason = resolve_one(yt, entry)

        if result:
            resolved.append(result)
            status = f"OK   {result['video_id']}"
        else:
            failed.append({**entry, "reason": reason})
            status = f"FAIL {reason}"

        print(f"[{i}/{len(todo)}] {entry['song']} — {entry['artist']}  ->  {status}")

        # Checkpoint every 10 songs so a crash is cheap
        if i % 10 == 0 or i == len(todo):
            save_json(args.urls, resolved)
            save_json(args.failed, failed)

        time.sleep(args.sleep)

    save_json(args.urls, resolved)
    save_json(args.failed, failed)
    print(f"\nDone. Resolved: {len(resolved)}   Failed: {len(failed)}")


if __name__ == "__main__":
    main()
