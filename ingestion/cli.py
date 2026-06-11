import argparse
import asyncio
import logging
import sys

from ingestion.pipeline import run_fetch, run_load, run_preview, run_stage


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m ingestion",
        description="Pharmacy drug ingestion pipeline.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="Fetch raw drug data into data/raw/.")
    fetch.add_argument(
        "--refresh",
        action="store_true",
        help="Ignore on-disk cache and re-fetch every drug.",
    )
    fetch.add_argument(
        "--limit", type=int, default=None, help="Only fetch first N drugs (debug)."
    )

    stage = sub.add_parser(
        "stage",
        help="Extract + normalize data/raw/ into data/staged/ and write PREVIEW.md.",
    )
    stage.add_argument(
        "--skip-db-diff",
        action="store_true",
        help="Do not connect to the DB to diff staged vs. current rows.",
    )

    sub.add_parser(
        "preview",
        help="Re-generate PREVIEW.md from existing data/staged/ without re-running stage.",
    )

    load = sub.add_parser(
        "load",
        help="Upsert data/staged/ into the database. Requires --confirm.",
    )
    load.add_argument(
        "--confirm",
        action="store_true",
        help="Actually commit the transaction. Without this, runs --dry-run.",
    )
    load.add_argument(
        "--dry-run",
        action="store_true",
        help="Open a transaction, perform upserts, then ROLLBACK. Implied without --confirm.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # httpx logs every request URL at INFO, including any query-string secrets.
    # Bump it to WARNING by default; -v re-enables full request logs.
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)

    if args.command == "fetch":
        return asyncio.run(run_fetch(refresh=args.refresh, limit=args.limit))
    if args.command == "stage":
        return asyncio.run(run_stage(skip_db_diff=args.skip_db_diff))
    if args.command == "preview":
        return run_preview()
    if args.command == "load":
        confirmed = args.confirm and not args.dry_run
        return asyncio.run(run_load(confirm=confirmed))
    return 2


if __name__ == "__main__":
    sys.exit(main())
