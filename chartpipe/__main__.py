import argparse
from pathlib import Path

from . import sync, bootstrap


def main():
    p = argparse.ArgumentParser(prog="chartpipe")
    sub = p.add_subparsers(dest="cmd", required=True)

    # sync
    s = sub.add_parser("sync", help="Incremental weekly sync")
    s.add_argument("backup", type=Path, help="NewPipe backup zip")
    s.add_argument("-o", "--out", type=Path, default=Path("NewPipeData-out.zip"))
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--no-refresh", action="store_true",
                   help="Use cached recent.json instead of re-fetching")

    # bootstrap
    b = sub.add_parser("bootstrap", help="One-time historical resolve")
    b.add_argument("--since", type=str, default=None, help="YYYY-MM-DD cutoff")
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--dry-run", action="store_true")
    b.add_argument("--refresh", action="store_true",
                   help="Re-download all.json even if cached")

    args = p.parse_args()

    if args.cmd == "sync":
        sync.run(args.backup, args.out,
                 dry_run=args.dry_run,
                 refresh=not args.no_refresh)
    elif args.cmd == "bootstrap":
        bootstrap.run(since=args.since, limit=args.limit,
                      dry_run=args.dry_run, refresh=args.refresh)


if __name__ == "__main__":
    main()
