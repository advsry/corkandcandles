#!/usr/bin/env python3
"""
Load Bookeo bookings into Azure SQL Database.
Fetches bookings for each month starting January 1, 2026.
Uses Bookeo API: https://api.bookeo.com/v2/bookings
API constraint: max 31 days per startTime/endTime range.
"""

import os
import sys
from pathlib import Path

# Allow importing booking_db from same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
import json
import argparse
from datetime import datetime, timedelta
from calendar import monthrange
from typing import Generator, Tuple, List, Dict, Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

# Bookeo API config
BOOKEO_BASE_URL = "https://api.bookeo.com/v2/bookings"
BOOKEO_API_KEY = os.getenv("BOOKEO_API_KEY", "A6ARNP4XEPX7CKKURW37L41567MXJW3H19A30869364")
BOOKEO_SECRET_KEY = os.getenv("BOOKEO_SECRET_KEY", "jrvcV0dTrGLKvC1hFs3SSnClISWiQsvo")
ITEMS_PER_PAGE = 100

# Azure SQL config
AZURE_SQL_SERVER = os.getenv("AZURE_SQL_SERVER")  # e.g. corkandcandles-sqlserver.database.windows.net
AZURE_SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "corkandcandles-bookings")
AZURE_SQL_USER = os.getenv("AZURE_SQL_USER")
AZURE_SQL_PASSWORD = os.getenv("AZURE_SQL_PASSWORD")
AZURE_SQL_DRIVER = "{ODBC Driver 18 for SQL Server}"


def get_date_ranges(
    start: datetime,
    end: datetime,
    max_days: int = 31,
) -> Generator[Tuple[datetime, datetime], None, None]:
    """Generate (start, end) ranges of max_days length. Bookeo API limit is 31 days."""
    current = start
    while current < end:
        chunk_end = min(current + timedelta(days=max_days), end)
        yield current, chunk_end
        current = chunk_end


def get_month_ranges(start_year: int, start_month: int, num_months: int) -> Generator[Tuple[datetime, datetime], None, None]:
    """Generate (start, end) datetimes for each month. End is exclusive (start of next month)."""
    year, month = start_year, start_month
    for _ in range(num_months):
        last_day = monthrange(year, month)[1]
        start = datetime(year, month, 1, tzinfo=None)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=None)
        else:
            end = datetime(year, month + 1, 1, tzinfo=None)
        yield start, end
        month += 1
        if month > 12:
            month = 1
            year += 1


def fetch_bookings_for_range(
    start: datetime,
    end: datetime,
    api_key: str = BOOKEO_API_KEY,
    secret_key: str = BOOKEO_SECRET_KEY,
    include_canceled: bool = True,
) -> List[Dict[str, Any]]:
    """Fetch all bookings from Bookeo API for a date range. Handles pagination."""
    all_bookings = []
    page = 1
    total_pages = 1

    start_str = start.strftime("%Y-%m-%dT00:00:00Z")
    end_str = end.strftime("%Y-%m-%dT00:00:00Z")

    while page <= total_pages:
        params = {
            "apiKey": api_key,
            "secretKey": secret_key,
            "startTime": start_str,
            "endTime": end_str,
            "itemsPerPage": ITEMS_PER_PAGE,
            "pageNumber": page,
            "includeCanceled": str(include_canceled).lower(),
        }
        url = f"{BOOKEO_BASE_URL}?{urlencode(params)}"

        try:
            resp = requests.get(url, timeout=3000)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            print(f"API error for {start_str}–{end_str} page {page}: {e}", file=sys.stderr)
            break
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}", file=sys.stderr)
            break

        bookings = data.get("data", [])
        info = data.get("info", {})
        total_pages = info.get("totalPages", 1)
        total_items = info.get("totalItems", 0)

        all_bookings.extend(bookings)
        print(f"  Fetched page {page}/{total_pages}: {len(bookings)} bookings (total so far: {len(all_bookings)})")

        if page >= total_pages:
            break
        page += 1

    return all_bookings


from booking_db import (
    create_bookings_table_if_not_exists,
    create_sync_state_table_if_not_exists,
    get_connection as get_db_connection,
    get_last_sync_time,
    parse_booking_for_db,
    set_last_sync_time,
    upsert_bookings_batch,
)


def main():
    parser = argparse.ArgumentParser(description="Load Bookeo bookings into Azure SQL")
    parser.add_argument(
        "--months",
        type=int,
        default=24,
        help="Number of months to fetch starting Jan 2026 (default: 24)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Fetch only new/updated bookings since last sync (for hourly runs)",
    )
    parser.add_argument(
        "--fetch-only",
        action="store_true",
        help="Only fetch from API, don't load to database",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Write fetched JSON to file instead of loading to DB",
    )
    args = parser.parse_args()

    if args.incremental:
        _run_incremental_sync(args)
        return

    print(f"Fetching bookings for {args.months} months starting January 2026...")
    all_bookings = []
    for start, end in get_month_ranges(2026, 1, args.months):
        label = start.strftime("%Y-%m")
        print(f"\nMonth {label}:")
        bookings = fetch_bookings_for_range(start, end)
        all_bookings.extend(bookings)
        print(f"  Month total: {len(bookings)} bookings")

    print(f"\nTotal bookings fetched: {len(all_bookings)}")

    if args.output:
        with open(args.output, "w") as f:
            json.dump(all_bookings, f, indent=2)
        print(f"Written to {args.output}")
        return

    if args.fetch_only:
        return

    # Load to Azure SQL
    if not all([AZURE_SQL_SERVER, AZURE_SQL_USER, AZURE_SQL_PASSWORD]):
        print(
            "\nAzure SQL credentials not set. Set AZURE_SQL_SERVER, AZURE_SQL_USER, AZURE_SQL_PASSWORD.",
            file=sys.stderr,
        )
        print("Use --fetch-only or --output FILE to skip database load.", file=sys.stderr)
        sys.exit(1)

    try:
        import pyodbc  # noqa: F401
    except ImportError:
        print("Install pyodbc: pip install pyodbc", file=sys.stderr)
        sys.exit(1)

    conn = get_db_connection()

    print("Ensuring Bookings table exists...")
    create_bookings_table_if_not_exists(conn)

    rows = [parse_booking_for_db(b) for b in all_bookings]
    rows = [r for r in rows if r["booking_number"]]
    inserted = upsert_bookings_batch(conn, rows)
    create_sync_state_table_if_not_exists(conn)
    set_last_sync_time(conn, datetime.utcnow())
    conn.close()
    print(f"\nUpserted {inserted} bookings to Azure SQL. Hourly sync will fetch from now.")


def _run_incremental_sync(args) -> None:
    """Fetch bookings since last sync. Designed for hourly cron/scheduler runs."""
    if not all([AZURE_SQL_SERVER, AZURE_SQL_USER, AZURE_SQL_PASSWORD]):
        print(
            "Azure SQL credentials not set. Set AZURE_SQL_SERVER, AZURE_SQL_USER, AZURE_SQL_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import pyodbc  # noqa: F401
    except ImportError:
        print("Install pyodbc: pip install pyodbc", file=sys.stderr)
        sys.exit(1)

    conn = get_db_connection()
    create_bookings_table_if_not_exists(conn)
    create_sync_state_table_if_not_exists(conn)

    now = datetime.utcnow()
    last_sync = get_last_sync_time(conn)

    # First run: fetch last 24h + next 90 days. Subsequent: fetch from last_sync to now+90d
    if last_sync:
        start_range = last_sync
        print(f"Incremental sync: fetching since {start_range.isoformat()}...")
    else:
        start_range = now - timedelta(hours=24)
        print(f"First incremental sync: fetching from {start_range.isoformat()}...")

    end_range = now + timedelta(days=90)
    all_bookings = []
    for start, end in get_date_ranges(start_range, end_range, max_days=31):
        label = f"{start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"
        print(f"  Range {label}:")
        bookings = fetch_bookings_for_range(start, end)
        all_bookings.extend(bookings)
        print(f"    {len(bookings)} bookings")

    print(f"\nTotal bookings fetched: {len(all_bookings)}")

    if args.fetch_only:
        conn.close()
        return

    rows = [parse_booking_for_db(b) for b in all_bookings]
    rows = [r for r in rows if r["booking_number"]]
    inserted = upsert_bookings_batch(conn, rows)
    set_last_sync_time(conn, now)
    conn.close()
    print(f"Upserted {inserted} bookings. Next sync will fetch from {now.isoformat()}.")


if __name__ == "__main__":
    main()
