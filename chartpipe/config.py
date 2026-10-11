from pathlib import Path
import os

ROOT = Path(__file__).resolve().parent.parent

# Data files (gitignored)
ALL_JSON    = ROOT / "all.json"
RECENT_JSON = ROOT / "recent.json"
MASTER_JSON = ROOT / "master.json"
URLS_JSON   = ROOT / "urls.json"
FAILED_JSON = ROOT / "failed.json"

# Billboard source
BILLBOARD_BASE  = "https://raw.githubusercontent.com/mhollingshead/billboard-hot-100/refs/heads/main"
ALL_JSON_URL    = f"{BILLBOARD_BASE}/all.json"
RECENT_JSON_URL = f"{BILLBOARD_BASE}/recent.json"

# NewPipe constants
SERVICE_ID_YOUTUBE = 0
STREAM_TYPE_VIDEO  = "VIDEO_STREAM"
PLAYLIST_NAME      = os.environ.get("CHARTPIPE_PLAYLIST", "Billboard Hot 100")

# Resolver tuning
SEARCH_SLEEP = float(os.environ.get("CHARTPIPE_SLEEP", "1.5"))
SEARCH_TOP_N = 5
