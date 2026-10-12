"""Bootstrap: fetch all.json, build master, resolve everything, inject."""
import json
import time

from ytmusicapi import YTMusic

from . import config, billboard, resolver, sync


def run(since: str | None = None, limit: int | None = None,
        dry_run: bool = False, refresh: bool = False) -> dict:
    print("Loading all.json …", flush=True)
    charts = billboard.fetch_all(refresh=refresh)
    master = billboard.build_master(charts)
    config.MASTER_JSON.write_text(json.dumps(master, indent=2, ensure_ascii=False))
    print(f"Master: {len(master)} songs", flush=True)

    urls = sync.load_urls()
    known = {sync._song_key(u["song"], u["artist"]) for u in urls}

    todo = [
        e for e in master
        if (not since or e["first_seen"] >= since)
        and sync._song_key(e["song"], e["artist"]) not in known
    ]
    if limit:
        todo = todo[:limit]

    est_min = len(todo) * (config.SEARCH_SLEEP + 0.4) / 60
    print(f"To resolve: {len(todo)}  (~{est_min:.0f} min)", flush=True)

    if dry_run or not todo:
        return {"todo": len(todo)}

    yt = YTMusic()
    for i, entry in enumerate(todo, 1):
        result, reason = resolver.resolve_one(yt, entry)
        if result:
            urls.insert(0, result)
        status = "OK" if result else f"FAIL {reason}"
        print(f"[{i}/{len(todo)}] {entry['song']} — {entry['artist']}  {status}", flush=True)
        time.sleep(config.SEARCH_SLEEP)
        if i % 10 == 0:
            sync.save_urls(urls)

    sync.save_urls(urls)
    return {"resolved": len(urls)}
