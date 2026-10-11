# Chartpipe

Sync the Billboard Hot 100 chart into a NewPipe playlist — automatically.

Chartpipe fetches the weekly Billboard chart, resolves each song to a YouTube
URL via YouTube Music, and injects the results into a NewPipe database backup.
Over time, your playlist becomes a growing archive of every song that charted.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
- [Project Layout](#project-layout)
- [Data Files](#data-files)
- [How the Pipeline Works](#how-the-pipeline-works)
- [Design Decisions](#design-decisions)
- [Troubleshooting](#troubleshooting)
- [Environment Variables](#environment-variables)

---

## How It Works

The pipeline has three stages, each handled by a separate module:

```
Billboard JSON  →  YouTube URLs  →  NewPipe DB  →  App
    (parse)         (resolve)        (inject)
```

1. **Parse** — Fetch the Billboard chart JSON from GitHub. Walk it newest-first,
   deduplicate by `(song, artist)`, and produce a master list.

2. **Resolve** — For each song not already cached, search YouTube Music, validate
   the artist match, and store the resulting video URL in `urls.json`.

3. **Inject** — Write every cached URL into a copy of your NewPipe database,
   attach them to a playlist, and repackage as a new backup zip.

Because resolved songs are cached, weekly runs only process genuinely new chart
entries — usually 5–25 songs, taking under a minute.

---

## Installation

Requires **Python 3.10+**.

```bash
git clone <your-repo-url>
cd billboard-newpipe-sync

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

Verify the install:

```bash
python -c "import ytmusicapi; print(ytmusicapi.__version__)"
```

---

## Quick Start

### First time ever

Export a backup from NewPipe (**Settings → Backup and restore → Export
database**) and copy it to your machine. Call it `NewPipeData-in.zip`.

Then run a bootstrap to build your initial song cache:

```bash
# Songs from 2015 onward — roughly 3 hours
python -m chartpipe bootstrap --since 2015-01-01
```

Run it in `tmux` so an SSH disconnect doesn't kill it:

```bash
tmux new -s bootstrap
python -m chartpipe bootstrap --since 2015-01-01
# Ctrl-B, then D to detach
# tmux attach -t bootstrap to check on it later
```

When it finishes, run a sync to inject everything into NewPipe:

```bash
python -m chartpipe sync NewPipeData-in.zip
```

Import `NewPipeData-out.zip` into NewPipe via **Settings → Backup and restore →
Import database**. Force-close NewPipe first.

### Every week after that

```bash
# Export a fresh backup from NewPipe → save as NewPipeData-in.zip
python -m chartpipe sync NewPipeData-in.zip

# Import NewPipeData-out.zip into NewPipe
```

That's it. Only the new chart entries get resolved, and the playlist grows.

---

## Commands

### `sync`

Incremental update — the command you run weekly.

```bash
python -m chartpipe sync NewPipeData-in.zip
```

| Flag              | Effect                                            |
| ----------------- | ------------------------------------------------- |
| `-o`, `--out PATH`| Output zip path (default: `NewPipeData-out.zip`)  |
| `--dry-run`       | Show what would resolve; no API calls, no DB write |
| `--no-refresh`    | Use cached `recent.json` instead of re-downloading |

**Example — see what sync would do without running it:**

```bash
python -m chartpipe sync NewPipeData-in.zip --dry-run
```

Output:

```
Chart date: 2026-10-10
Cache: 100 songs
New songs: 5
  would resolve: Patient Zero — Taylor Swift
  ...
```

### `bootstrap`

One-time historical load. Fetches `all.json`, builds the master song list, and
resolves everything in scope.

```bash
python -m chartpipe bootstrap --since 2015-01-01
```

| Flag               | Effect                                             |
| ------------------ | -------------------------------------------------- |
| `--since YYYY-MM-DD` | Only resolve songs with `first_seen` on/after this date |
| `--limit N`        | Stop after N songs (for testing)                   |
| `--dry-run`        | List songs without resolving                       |
| `--refresh`        | Re-download `all.json` even if cached locally       |

**Examples:**

```bash
# Full history back to 1958 (~17 hours)
python -m chartpipe bootstrap --since 1958-01-01

# Small test — resolve only 20 songs
python -m chartpipe bootstrap --since 2026-01-01 --limit 20

# Force fresh download of all.json
python -m chartpipe bootstrap --since 2015-01-01 --refresh
```

`all.json` is 42 MB and mostly historical. By default, bootstrap reuses a locally
cached copy and only downloads it once. Use `--refresh` if you want the very
latest.

---

## Project Layout

```
chartpipe/                The package
├── __init__.py           Version marker
├── __main__.py           CLI entry point (argparse)
├── config.py             Paths, constants, environment variables
├── billboard.py          Fetch + parse Billboard JSON
├── resolver.py           YouTube Music search + artist validation
├── db.py                 NewPipe SQLite injection
├── sync.py               Incremental orchestrator (weekly)
└── bootstrap.py          Full-history orchestrator (one-time)

tests/                    Unit tests (planned)
pyproject.toml            Package metadata + `chartpipe` command
requirements.txt          Python dependencies
README.md                 This file
```

---

## Data Files

These are generated automatically and gitignored:

| File                  | Purpose                                                    |
| --------------------- | ---------------------------------------------------------- |
| `all.json`            | Raw Billboard history dump (~42 MB)                        |
| `recent.json`         | Current week's chart (small, re-fetched each sync)         |
| `master.json`         | Deduplicated song list, newest-first                       |
| `urls.json`           | Song → YouTube URL cache (**the source of truth**)          |
| `failed.json`         | Songs that could not be resolved                           |
| `NewPipeData-in.zip`  | Your NewPipe backup — input to `sync`                      |
| `NewPipeData-out.zip` | Modified backup — output from `sync`, import back into app |
| `work_extract/`       | Temp directory during injection (auto-created/removed)     |

**`urls.json` is the most important file.** It holds every resolved song and is
never re-searched. Back it up before risky operations:

```bash
cp urls.json urls.json.bak
```

---

## How the Pipeline Works

### 1. Billboard parsing

The source repo publishes `all.json` (every chart since 1958) and `recent.json`
(current week). Each chart is a JSON object like:

```json
{
  "date": "2026-10-10",
  "data": [
    {"song": "Patient Zero", "artist": "Taylor Swift", "this_week": 1, "...": "..."}
  ]
}
```

`build_master()` walks charts newest-first, keeping the **first** appearance of
each unique `(song, artist)` pair. The result is a newest-first master list.

### 2. Song resolution

For each song, `resolver.py` calls
`ytmusicapi.search(f"{song} {artist}", filter="songs")`. It then validates that
the returned artist matches the Billboard artist (case-insensitive,
diacritic-stripped substring match).

This catches common failures automatically:

- Covers by unknown artists (rejected — artist mismatch)
- Karaoke tracks (rejected — artist mismatch)
- Diacritic differences like `ADELA` vs `ADÉLA` (accepted — normalized)

If the top result fails validation, the next few results are tried (up to
`SEARCH_TOP_N`, default 5).

### 3. Database injection

The NewPipe database is SQLite with three relevant tables:

- **`streams`** — the actual videos (URL, title, duration, uploader)
- **`playlists`** — playlist metadata (name, display index)
- **`playlist_stream_join`** — links streams to playlists with a `join_index`

Injection:

1. Opens the `newpipe.db` from the extracted backup
2. Finds or creates the target playlist
3. Deletes all existing membership rows for that playlist
4. Re-inserts every song in master order (`INSERT OR IGNORE` on streams to
   reuse existing rows by `(service_id, url)`)
5. Commits and repackages the zip

It's **idempotent** — running twice gives the same result.

---

## Design Decisions

**Append-only URL cache.**
Once a song has a resolved URL, it's never re-searched. YouTube matches drift,
and re-running a full resolve would cost hours with no benefit. The cache is
the source of truth.

**Idempotent injection.**
Every sync rebuilds the playlist from scratch instead of appending. This means
no duplicates, no ordering drift, and running twice is safe.

**Accumulative archive.**
The playlist grows over time. Songs that drop off the chart stay in your
playlist. Alternative: snapshot mode (current 100 only) — not implemented, but
easy to add by filtering on the current chart before injection.

**Newest-first ordering.**
The master list is sorted newest-first, and injection preserves that order. So
the playlist always shows the most recent songs at the top.

**Unauthenticated ytmusicapi.**
Works on residential IPs without browser cookies. If you run this from a data
center (AWS, GitHub Actions, etc.), YouTube will block search requests. Use a
home server or residential connection.

**No "official" keyword in searches.**
Keyword-stuffing degrades ytmusicapi's relevance ranking. The `filter="songs"`
parameter is the right way to constrain results to music tracks.

---

## Troubleshooting

### "No module named 'ytmusicapi'"

The virtual environment isn't active, or the package isn't installed:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### "api_error: 429" or rate limit errors

YouTube is throttling. Increase the sleep between requests:

```bash
CHARTPIPE_SLEEP=3 python -m chartpipe sync NewPipeData-in.zip
```

### "artist_mismatch" failures

The resolver rejected the top result because the artist didn't match. Check
`failed.json` — most are fixable by extending the top-N search, or by manual
intervention. See the resolver's `SEARCH_TOP_N` constant.

### Import fails in NewPipe

- Force-close NewPipe completely before importing (swipe from recents)
- Make sure the file is a valid `NewPipeData-*.zip`
- Try restoring your original backup first, then re-importing

### Playlist appears but is empty

Check the DB before repackaging:

```bash
mkdir -p /tmp/check && cd /tmp/check
unzip -o ~/devops/billboard-newpipe-sync/NewPipeData-out.zip
sqlite3 newpipe.db "
  SELECT COUNT(*) FROM playlist_stream_join
  WHERE playlist_id = (SELECT uid FROM playlists WHERE name='Billboard Hot 100');
"
```

### Lost `urls.json`

The cache is the only thing that makes sync fast. If you lose it:

1. Restore from a backup if you have one (`urls.json.bak`)
2. Or extract URLs from an existing `NewPipeData-out.zip`'s database
3. Or re-run `bootstrap` (slow — hours)

---

## Environment Variables

| Variable             | Default             | Purpose                              |
| -------------------- | ------------------- | ------------------------------------ |
| `CHARTPIPE_PLAYLIST` | `Billboard Hot 100` | Name of the target NewPipe playlist  |
| `CHARTPIPE_SLEEP`    | `1.5`               | Seconds between ytmusicapi searches  |

---

## Requirements

- Python 3.10+
- `ytmusicapi` (installed via `requirements.txt`)
- A NewPipe backup (`.zip`)
- A residential IP (YouTube blocks data-center IPs)

---

## Roadmap

Completed:

- [x] Billboard parser
- [x] YouTube URL resolver with artist validation
- [x] NewPipe database injection
- [x] CLI package structure
- [x] Incremental sync
- [x] Local JSON caching

Planned:

- [ ] Docker containerization
- [ ] systemd timer for weekly automation
- [ ] Notifications (ntfy / Discord)
- [ ] Unit tests + GitHub Actions CI
- [ ] Docker image published to GHCR

---

## License

Personal project — no license specified.
