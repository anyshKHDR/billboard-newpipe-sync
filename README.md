# Chartpipe

Sync the Billboard Hot 100 chart into a NewPipe playlist — automatically.

Chartpipe fetches the weekly Billboard chart, resolves each song to a YouTube
URL via YouTube Music, and injects the results into a NewPipe database backup.
Songs are cached, so weekly runs only process genuinely new chart entries.

**Features:**

- Incremental sync — only resolves new songs (~5–25 per week)
- Automatic artist validation (rejects covers, karaoke, wrong matches)
- Idempotent — safe to run repeatedly, no duplicates
- Accumulative — songs stay in the playlist after dropping off the chart
- Fully automated via Docker + systemd

---

## How It Works

```
Billboard JSON  →  YouTube URLs  →  NewPipe DB  →  App
    (parse)         (resolve)        (inject)
```

1. **Parse** — Fetch the current Billboard chart from GitHub
2. **Resolve** — Search YouTube Music for each new song, cache the video URL
3. **Inject** — Write all cached URLs into a copy of your NewPipe database

The resolved-URL cache lives in `urls.json` and is never re-searched.

---

## Quick Start

### 1. Install

```bash
git clone <your-repo-url>
cd billboard-newpipe-sync

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Requires **Python 3.10+**.

### 2. Export a NewPipe backup

On your phone: **Settings → Backup and restore → Export database**.
Copy the resulting `NewPipeData-*.zip` to your machine and rename it to
`NewPipeData-in.zip`.

### 3. Bootstrap the cache (first time only)

Resolves historical songs. Takes hours — run in `tmux`.

```bash
tmux new -s bootstrap
python -m chartpipe bootstrap --since 2015-01-01
# Ctrl-B, then D to detach
```

For a quick test, use `--limit 20`.

### 4. Sync and import

```bash
python -m chartpipe sync NewPipeData-in.zip
```

This produces `NewPipeData-out.zip`. Import it into NewPipe
(**Settings → Backup and restore → Import database**). Force-close NewPipe first.

### 5. Every week after that

```bash
# Export fresh backup from phone → save as NewPipeData-in.zip
python -m chartpipe sync NewPipeData-in.zip
# Import NewPipeData-out.zip into NewPipe
```

Only new songs are resolved. The playlist grows.

---

## Commands

### `sync` — incremental update (run weekly)

```bash
python -m chartpipe sync NewPipeData-in.zip
```

| Flag              | Effect                                             |
| ----------------- | -------------------------------------------------- |
| `-o`, `--out PATH`| Output zip path (default: `NewPipeData-out.zip`)   |
| `--dry-run`       | Preview only — no API calls, no DB writes          |
| `--no-refresh`    | Use cached `recent.json` instead of re-downloading |

### `bootstrap` — one-time historical load

```bash
python -m chartpipe bootstrap --since 2015-01-01
```

| Flag                 | Effect                                          |
| -------------------- | ----------------------------------------------- |
| `--since YYYY-MM-DD` | Only resolve songs appearing on/after this date |
| `--limit N`          | Stop after N songs (for testing)                |
| `--dry-run`          | List without resolving                          |
| `--refresh`          | Re-download `all.json` even if cached           |

**Examples:**

```bash
python -m chartpipe bootstrap --since 1958-01-01              # full history (~17h)
python -m chartpipe bootstrap --since 2026-01-01 --limit 20   # quick test
```

---

## Docker

Build and run without a Python environment:

```bash
# Build the image
docker compose build

# Dry run
docker compose run --rm chartpipe sync /data/NewPipeData-in.zip --dry-run

# Real run
docker compose run --rm chartpipe sync /data/NewPipeData-in.zip \
                                    -o /data/NewPipeData-out.zip
```

The project directory is mounted at `/data` inside the container. Pull
pre-built images from GHCR with:

```bash
docker run --rm -v ~/chartpipe-work:/data \
  ghcr.io/YOUR_USERNAME/chartpipe:latest \
  sync /data/NewPipeData-in.zip -o /data/NewPipeData-out.zip
```

---

## Automated Weekly Sync (systemd)

Install the timer so sync runs automatically every Wednesday:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/chartpipe-sync.service systemd/chartpipe-sync.timer ~/.config/systemd/user/
cp systemd/weekly-sync.sh ~/chartpipe-work/weekly-sync.sh
chmod +x ~/chartpipe-work/weekly-sync.sh

systemctl --user daemon-reload
systemctl --user enable --now chartpipe-sync.timer

# Survive logout / run headless
sudo loginctl enable-linger $USER
```

See [`systemd/README.md`](systemd/README.md) for details.

**Weekly workflow once automated:**

1. Upload a fresh `NewPipeData-in.zip` to `~/chartpipe-work/`
2. systemd runs the sync unattended
3. Download `~/chartpipe-work/NewPipeData-out.zip` → import into NewPipe

---

## Project Layout

```
chartpipe/                Python package
├── __main__.py           CLI entry point
├── config.py             Paths, constants, env vars
├── billboard.py          Fetch + parse Billboard JSON
├── resolver.py           YouTube Music search + validation
├── db.py                 NewPipe SQLite injection
├── sync.py               Incremental orchestrator (weekly)
└── bootstrap.py          Historical load (one-time)

systemd/                  Deployment files
├── chartpipe-sync.service
├── chartpipe-sync.timer
└── weekly-sync.sh

Dockerfile                Container image
docker-compose.yml        Local dev / build
pyproject.toml            Package metadata
requirements.txt          Python dependencies
```

---

## Data Files

Generated automatically and gitignored:

| File                  | Purpose                                          |
| --------------------- | ------------------------------------------------ |
| `all.json`            | Raw Billboard history (~42 MB)                   |
| `recent.json`         | Current week's chart                             |
| `master.json`         | Deduplicated song list, newest-first             |
| `urls.json`           | Song → YouTube URL cache (**source of truth**)   |
| `failed.json`         | Songs that couldn't be resolved                  |
| `NewPipeData-*.zip`   | NewPipe backups (input/output)                   |

**`urls.json` is the most important file.** Back it up before risky operations:

```bash
cp urls.json urls.json.bak
```

---

## Design Notes

- **Append-only cache** — a resolved song is never re-searched
- **Idempotent injection** — every sync rebuilds the playlist from `urls.json`
- **Residential IP required** — YouTube blocks data-center IPs
- **Unauthenticated ytmusicapi** — no cookies or login required

---

## Environment Variables

| Variable             | Default             | Purpose                          |
| -------------------- | ------------------- | -------------------------------- |
| `CHARTPIPE_PLAYLIST` | `Billboard Hot 100` | Target NewPipe playlist name     |
| `CHARTPIPE_SLEEP`    | `1.5`               | Seconds between API searches     |
| `CHARTPIPE_DATA`     | project root        | Data directory (used by Docker)  |

---

## Troubleshooting

**`No module named 'ytmusicapi'`** — activate the venv and reinstall:

```bash
source .venv/bin/activate && pip install -r requirements.txt
```

**Rate-limited (`api_error: 429`)** — increase the sleep:

```bash
CHARTPIPE_SLEEP=3 python -m chartpipe sync NewPipeData-in.zip
```

**Import fails in NewPipe** — force-close the app first (swipe from recents),
then retry the import.

**Lost `urls.json`** — restore from `urls.json.bak`, extract URLs from an
existing `NewPipeData-out.zip`, or re-run `bootstrap`.

---

## Requirements

- Python 3.10+ (or Docker)
- A NewPipe backup (`.zip`)
- A residential IP (YouTube blocks cloud/datacenter IPs)

---

## License

Personal project — no license specified.
