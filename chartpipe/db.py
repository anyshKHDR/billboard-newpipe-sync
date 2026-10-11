import sqlite3
from pathlib import Path

from . import config

NO_THUMBNAIL_STREAM_ID = -1


def _get_or_create_playlist(conn: sqlite3.Connection, name: str) -> int:
    cur = conn.cursor()
    row = cur.execute("SELECT uid FROM playlists WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    next_idx = cur.execute(
        "SELECT COALESCE(MAX(display_index), -1) + 1 FROM playlists"
    ).fetchone()[0]
    cur.execute(
        "INSERT INTO playlists (name, is_thumbnail_permanent, thumbnail_stream_id, display_index)"
        " VALUES (?, 0, ?, ?)",
        (name, NO_THUMBNAIL_STREAM_ID, next_idx),
    )
    return cur.lastrowid


def _get_or_create_stream(conn: sqlite3.Connection, entry: dict) -> int:
    cur = conn.cursor()
    url = entry["url"]
    row = cur.execute(
        "SELECT uid FROM streams WHERE service_id = ? AND url = ?",
        (config.SERVICE_ID_YOUTUBE, url),
    ).fetchone()
    if row:
        return row[0]

    cur.execute(
        "INSERT INTO streams (service_id, url, title, stream_type, duration, uploader)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            config.SERVICE_ID_YOUTUBE,
            url,
            f"{entry['song']} — {entry['artist']}",
            config.STREAM_TYPE_VIDEO,
            entry.get("yt_duration") or 0,
            entry.get("artist") or "Unknown",
        ),
    )
    return cur.lastrowid


def inject(db_path: Path, urls: list[dict], playlist_name: str) -> dict:
    conn = sqlite3.connect(db_path)
    stats = {"playlist_id": None, "songs": 0}
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        playlist_id = _get_or_create_playlist(conn, playlist_name)
        stats["playlist_id"] = playlist_id

        cur.execute("DELETE FROM playlist_stream_join WHERE playlist_id = ?", (playlist_id,))

        for i, entry in enumerate(urls):
            sid = _get_or_create_stream(conn, entry)
            cur.execute(
                "INSERT INTO playlist_stream_join (playlist_id, stream_id, join_index)"
                " VALUES (?, ?, ?)",
                (playlist_id, sid, i),
            )
            stats["songs"] += 1

        conn.commit()
    finally:
        conn.close()
    return stats
