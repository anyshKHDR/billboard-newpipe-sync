import unicodedata
from ytmusicapi import YTMusic

from . import config


def strip_diacritics(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )


def artist_matches(billboard_artist: str, yt_artists: list[dict]) -> bool:
    bb = strip_diacritics(billboard_artist.lower())
    if not bb:
        return False
    for a in yt_artists:
        name = strip_diacritics((a.get("name") or "").lower())
        if name and (bb in name or name in bb):
            return True
    return False


def resolve_one(yt: YTMusic, entry: dict) -> tuple[dict | None, str | None]:
    query = f"{entry['song']} {entry['artist']}"
    try:
        results = yt.search(query, filter="songs")
    except Exception as e:
        return None, f"api_error: {e}"

    if not results:
        return None, "no_results"

    for i, candidate in enumerate(results[:config.SEARCH_TOP_N]):
        video_id = candidate.get("videoId")
        if not video_id:
            continue
        if not artist_matches(entry["artist"], candidate.get("artists") or []):
            continue
        return {
            "song": entry["song"],
            "artist": entry["artist"],
            "first_seen": entry["first_seen"],
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "yt_title": candidate.get("title"),
            "yt_duration": candidate.get("duration_seconds"),
            "match_rank": i,
        }, None

    top_artists = [a.get("name") for a in (results[0].get("artists") or [])]
    return None, f"no_match_in_top{config.SEARCH_TOP_N} (top was {top_artists})"
