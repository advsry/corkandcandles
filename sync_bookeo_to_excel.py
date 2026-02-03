#!/usr/bin/env python3
"""
Bookeo → Excel sync for Cork and Candles.

Fetches all bookings from Bookeo API from January 2026 through 90 days in the
future, and writes them to an Excel spreadsheet. Suitable for running on an
Azure VM (cron or Task Scheduler).

Usage:
  python sync_bookeo_to_excel.py [--config CONFIG_PATH] [--output OUTPUT.xlsx]

Config (config.json or env):
  api_key, secret_key: Bookeo API credentials
  historical_start: ISO datetime (default 2026-01-01)
  future_days: days from today to fetch (default 90)
  output_file: path to Excel file
  include_canceled: include canceled bookings (default true)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from bookeo_client import BookeoAPIError, BookeoClient
from excel_export import write_bookings_to_excel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DEFAULT_HISTORICAL_START = "2026-01-01T00:00:00Z"
DEFAULT_FUTURE_DAYS = 90
DEFAULT_OUTPUT_FILE = "bookeo_bookings.xlsx"


def load_config(path: str | Path | None = None) -> dict:
    """Load config from JSON file and environment variables."""
    config_path = path or Path("config.json")
    config: dict = {}

    if Path(config_path).exists():
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

    # Env overrides (for Azure VM / production)
    config["api_key"] = os.environ.get("apiKey") or config.get("apiKey")
    config["secret_key"] = os.environ.get("secretKey") or config.get("secretKey")
    config["historical_start"] = (
        os.environ.get("BOOKEO_HISTORICAL_START")
        or config.get("historical_start")
        or DEFAULT_HISTORICAL_START
    )
    config["future_days"] = int(
        os.environ.get("BOOKEO_FUTURE_DAYS")
        or config.get("future_days")
        or DEFAULT_FUTURE_DAYS
    )
    config["output_file"] = (
        os.environ.get("BOOKEO_OUTPUT_FILE")
        or config.get("output_file")
        or DEFAULT_OUTPUT_FILE
    )
    config["include_canceled"] = config.get("include_canceled", True)
    if isinstance(config["include_canceled"], str):
        config["include_canceled"] = config["include_canceled"].lower() in ("true", "1", "yes")

    return config


def parse_start(s: str) -> datetime:
    """Parse ISO datetime string to timezone-aware datetime."""
    if not s:
        raise ValueError("Empty historical_start")
    # Support Z or +00:00
    s = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Bookeo bookings to Excel (historical from Jan 2026 + 90 days future)."
    )
    parser.add_argument(
        "--config",
        "-c",
        default="config.json",
        help="Path to config JSON (default: config.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Override output Excel path",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only fetch and log count; do not write Excel",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    api_key = config.get("api_key")
    secret_key = config.get("secret_key")
    if not api_key or not secret_key:
        logger.error(
            "Missing api_key or secret_key. Set in config.json or BOOKEO_API_KEY / BOOKEO_SECRET_KEY."
        )
        return 1

    historical_start = parse_start(config["historical_start"])
    future_days = config["future_days"]
    now = datetime.now(timezone.utc)
    future_end = now + timedelta(days=future_days)
    output_file = args.output or config["output_file"]
    include_canceled = config["include_canceled"]

    logger.info(
        "Syncing bookings from %s to %s (future_days=%d)",
        historical_start.date(),
        future_end.date(),
        future_days,
    )

    client = BookeoClient(api_key=api_key, secret_key=secret_key)
    bookings: list[dict] = []
    try:
        for b in client.fetch_all_bookings(
            historical_start,
            future_end,
            include_canceled=include_canceled,
        ):
            bookings.append(b)
    except BookeoAPIError as e:
        logger.error("Bookeo API error: %s (status=%s)", e, e.status_code)
        if e.response:
            logger.error("Response: %s", e.response)
        return 1

    logger.info("Fetched %d bookings", len(bookings))

    if args.dry_run:
        logger.info("Dry run: skipping Excel write")
        return 0

    write_bookings_to_excel(bookings, output_file)
    logger.info("Done. Output: %s", Path(output_file).resolve())
    return 0


if __name__ == "__main__":
    sys.exit(main())
