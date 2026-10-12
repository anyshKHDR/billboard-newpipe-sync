"""Incremental sync: fetch recent chart, resolve new songs, inject."""
import json
import shutil
import time
import zipfile
from pathlib import Path

from ytmusicapi import YTMusic

from . import config, billboard, resolver, db


def _song_key(song: str, artist: str) -> str:
    return f"{song.lower()}||{artist.lower()}"


def load_urls() -> list[dict]:
    if not config.URLS_JSON.exists():
        return []
    return json.loads(config.URLS_JSON.read_text())


def save_urls(urls: list[dict]) -> None:
    tmp = config.URLS_JSON.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(urls, indent=2, ensure_ascii=False))
    tmp.replace(config.URLS_JSON)


def _find_new(urls: list[dict], chart: dict) -> list[dict]:
    known = {_song_key(u["song"], u["artist"]) for u in urls}
    return [
        {"song": s, "artist": a, "first_seen": chart["date"]}
        for s, a in billboard.extract_songs(chart)
        if _song_key(s, a) not in known
    ]


def run(backup_zip: Path, output_zip: Path,
        dry_run: bool = False, refresh: bool = True) -> dict:
    stats = {"chart_date": None, "new": 0, "resolved": 0, "failed": 0, "total": 0}

    # 1. Fetch current chart
    chart = billboard.fetch_recent(refresh=refresh)
    stats["chart_date"] = chart["date"]
    print(f"Chart date: {chart['date']}")

    # 2. Load cache and find new songs
    urls = load_urls()
    print(f"Cache: {len(urls)} songs")
    new = _find_new(urls, chart)
    stats["new"] = len(new)
    print(f"New songs: {len(new)}")

    if dry_run:
        for e in new:
            print(f"  would resolve: {e['song']} — {e['artist']}")
        return stats

    # 3. Resolve new songs (prepend to cache to keep newest-first)
    if new:
        yt = YTMusic()
        resolved_batch = []
        for i, entry in enumerate(new, 1):
            result, reason = resolver.resolve_one(yt, entry)
            if result:
                resolved_batch.append(result)
                stats["resolved"] += 1
                print(f"[{i}/{len(new)}] {entry['song']} — {entry['artist']}  OK")
            else:
                stats["failed"] += 1
                print(f"[{i}/{len(new)}] {entry['song']} — {entry['artist']}  FAIL {reason}")
            time.sleep(config.SEARCH_SLEEP)
            if i % 10 == 0:
                save_urls(list(reversed(resolved_batch)) + urls)
        urls = list(reversed(resolved_batch)) + urls
        save_urls(urls)

    # 4. Inject into NewPipe DB
    work = config.WORK_DIR
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(backup_zip) as zf:
        zf.extractall(work)

    db_path = work / "newpipe.db"
    if not db_path.exists():
        raise SystemExit(f"newpipe.db not found in {backup_zip}")

    inject_stats = db.inject(db_path, urls, config.PLAYLIST_NAME)
    stats["total"] = inject_stats["songs"]
    print(f"Playlist '{config.PLAYLIST_NAME}' uid={inject_stats['playlist_id']}, "
          f"{inject_stats['songs']} songs")

    # 5. Repackage
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(work.iterdir()):
            if f.is_file():
                zf.write(f, f.name)
    print(f"Wrote {output_zip}")

    shutil.rmtree(work)
    return stats
