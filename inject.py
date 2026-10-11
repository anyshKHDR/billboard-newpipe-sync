# inject.py
"""
Inject resolved Billboard URLs into a NewPipe database.

Idempotent: wipes and rebuilds the target playlist's membership each run,
so the resulting playlist always matches urls.json order (newest first).

Usage:
    python inject.py NewPipeData-*.zip --urls urls.json
"""

import json
import shutil
import sqlite3
import argparse
import zipfile
from pathlib import Path

SERVICE_ID_YOUTUBE = 0
STREAM_TYPE_VIDEO = "VIDEO_STREAM"
PLAYLIST_NAME_DEFAULT = "Billboard Hot 100"

# NewPipe uses -1 for "playlist has no thumbnail stream"
NO_THUMBNAIL_STREAM_ID = -1


def load_urls(path: Path) -> list[dict]:
    return json.loads(path.read_text())


def get_or_create_playlist(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.cursor()
    row = cur.execute("SELECT uid FROM playlists WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]

    next_display_index = cur.execute(
        "SELECT COALESCE(MAX(display_index), -1) + 1 FROM playlists"
    ).fetchone()[0]

    cur.execute(
        """
        INSERT INTO playlists
          (name, is_thumbnail_permanent, thumbnail_stream_id, display_index)
        VALUES (?, 0, ?, ?)
        """,
        (name, NO_THUMBNAIL_STREAM_ID, next_display_index),
    )
    return cur.lastrowid


def get_or_create_stream(conn: sqlite3.Connection, entry: dict) -> int:
    cur = conn.cursor()
    url = entry["url"]

    row = cur.execute(
        "SELECT uid FROM streams WHERE service_id = ? AND url = ?",
        (SERVICE_ID_YOUTUBE, url),
    ).fetchone()
    if row:
        return row[0]

    # NewPipe's NOT NULL columns need non-None values
    duration = entry.get("yt_duration") or 0
    uploader = entry.get("artist") or "Unknown"
    title = f"{entry['song']} — {entry['artist']}"

    cur.execute(
        """
        INSERT INTO streams
          (service_id, url, title, stream_type, duration, uploader)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (SERVICE_ID_YOUTUBE, url, title, STREAM_TYPE_VIDEO, duration, uploader),
    )
    return cur.lastrowid


def inject(db_path: Path, urls: list[dict], playlist_name: str) -> dict:
    conn = sqlite3.connect(db_path)
    stats = {"playlist_id": None, "streams_inserted": 0, "join_rows": 0}
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")

        playlist_id = get_or_create_playlist(conn, playlist_name)
        stats["playlist_id"] = playlist_id

        # Rebuild membership: wipe, then insert in the master order
        cur.execute(
            "DELETE FROM playlist_stream_join WHERE playlist_id = ?", (playlist_id,)
        )

        for i, entry in enumerate(urls):
            stream_id = get_or_create_stream(conn, entry)
            cur.execute(
                """
                INSERT INTO playlist_stream_join
                  (playlist_id, stream_id, join_index)
                VALUES (?, ?, ?)
                """,
                (playlist_id, stream_id, i),
            )
            stats["join_rows"] += 1

        conn.commit()
    finally:
        conn.close()
    return stats


def repackage(src_dir: Path, out_zip: Path):
    """Zip every file in src_dir (newpipe.db + settings + preferences.json)."""
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(src_dir.iterdir()):
            if f.is_file():
                zf.write(f, f.name)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("backup", type=Path, help="NewPipe backup zip")
    p.add_argument("--urls", type=Path, default=Path("urls.json"))
    p.add_argument("--playlist", default=PLAYLIST_NAME_DEFAULT)
    p.add_argument("--out", type=Path, default=Path("NewPipeData-out.zip"))
    p.add_argument("--work", type=Path, default=Path("work_extract"))
    args = p.parse_args()

    if args.work.exists():
        shutil.rmtree(args.work)
    args.work.mkdir()

    print(f"Extracting {args.backup} → {args.work}")
    with zipfile.ZipFile(args.backup) as zf:
        zf.extractall(args.work)

    db = args.work / "newpipe.db"
    if not db.exists():
        raise SystemExit(f"newpipe.db not found in {args.backup}")

    urls = load_urls(args.urls)
    print(f"Loaded {len(urls)} resolved songs from {args.urls}")

    stats = inject(db, urls, args.playlist)
    print(f"Playlist '{args.playlist}' uid={stats['playlist_id']}")
    print(f"Added {stats['join_rows']} songs to playlist")

    repackage(args.work, args.out)
    print(f"Wrote {args.out}")
    print(f"\nImport this file via NewPipe → Settings → Backup and restore")


if __name__ == "__main__":
    main()
