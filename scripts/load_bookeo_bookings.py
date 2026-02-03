#!/usr/bin/env python3
"""
Load Bookeo bookings into Azure SQL Database.
Fetches bookings for each month starting January 1, 2026.
Uses Bookeo API: https://api.bookeo.com/v2/bookings
API constraint: max 31 days per startTime/endTime range.
"""

import os
import sys
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
            resp = requests.get(url, timeout=30)
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


def parse_booking_for_db(booking: Dict[str, Any]) -> Dict[str, Any]:
    """Extract fields for database insert."""
    participants = booking.get("participants", {})
    numbers = participants.get("numbers", [])
    total_participants = sum(n.get("number", 0) for n in numbers)

    price = booking.get("price", {})
    total_gross = price.get("totalGross", {}).get("amount")
    total_net = price.get("totalNet", {}).get("amount")
    total_paid = price.get("totalPaid", {}).get("amount")
    currency = price.get("totalGross", {}).get("currency")

    last_change = booking.get("lastChangeTime")

    return {
        "booking_number": booking.get("bookingNumber"),
        "event_id": booking.get("eventId"),
        "start_time": booking.get("startTime"),
        "end_time": booking.get("endTime"),
        "customer_id": booking.get("customerId"),
        "title": booking.get("title"),
        "product_name": booking.get("productName"),
        "product_id": booking.get("productId"),
        "canceled": 1 if booking.get("canceled") else 0,
        "accepted": 1 if booking.get("accepted", True) else 0,
        "no_show": 1 if booking.get("noShow") else 0,
        "private_event": 1 if booking.get("privateEvent") else 0,
        "source_ip": booking.get("sourceIp"),
        "creation_time": booking.get("creationTime"),
        "last_change_time": last_change,
        "last_change_agent": booking.get("lastChangeAgent"),
        "total_participants": total_participants,
        "total_gross": str(total_gross) if total_gross is not None else None,
        "total_net": str(total_net) if total_net is not None else None,
        "total_paid": str(total_paid) if total_paid is not None else None,
        "currency": currency,
        "raw_json": json.dumps(booking) if booking else None,
    }


def upsert_to_azure_sql(rows: List[Dict[str, Any]], conn) -> int:
    """Insert or update bookings in Azure SQL."""
    if not rows:
        return 0

    cursor = conn.cursor()
    update_sql = """
    UPDATE Bookings SET
        event_id=?, start_time=?, end_time=?, customer_id=?, title=?,
        product_name=?, product_id=?, canceled=?, accepted=?, no_show=?,
        private_event=?, source_ip=?, creation_time=?, last_change_time=?,
        last_change_agent=?, total_participants=?, total_gross=?, total_net=?,
        total_paid=?, currency=?, raw_json=?, updated_at=SYSDATETIMEOFFSET()
    WHERE booking_number=?
    """
    insert_sql = """
    INSERT INTO Bookings (booking_number, event_id, start_time, end_time, customer_id, title,
            product_name, product_id, canceled, accepted, no_show, private_event,
            source_ip, creation_time, last_change_time, last_change_agent,
            total_participants, total_gross, total_net, total_paid, currency, raw_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    count = 0
    for r in rows:
        params = (
            r["event_id"], r["start_time"], r["end_time"], r["customer_id"], r["title"],
            r["product_name"], r["product_id"], r["canceled"], r["accepted"], r["no_show"],
            r["private_event"], r["source_ip"], r["creation_time"], r["last_change_time"],
            r["last_change_agent"], r["total_participants"], r["total_gross"], r["total_net"],
            r["total_paid"], r["currency"], r["raw_json"], r["booking_number"],
        )
        cursor.execute(update_sql, params)
        if cursor.rowcount == 0:
            cursor.execute(
                insert_sql,
                (
                    r["booking_number"], r["event_id"], r["start_time"], r["end_time"],
                    r["customer_id"], r["title"], r["product_name"], r["product_id"],
                    r["canceled"], r["accepted"], r["no_show"], r["private_event"],
                    r["source_ip"], r["creation_time"], r["last_change_time"], r["last_change_agent"],
                    r["total_participants"], r["total_gross"], r["total_net"], r["total_paid"],
                    r["currency"], r["raw_json"],
                ),
            )
        count += 1
    conn.commit()
    cursor.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="Load Bookeo bookings into Azure SQL")
    parser.add_argument(
        "--months",
        type=int,
        default=24,
        help="Number of months to fetch starting Jan 2026 (default: 24)",
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
        import pyodbc
    except ImportError:
        print("Install pyodbc: pip install pyodbc", file=sys.stderr)
        sys.exit(1)

    conn_str = (
        f"Driver={AZURE_SQL_DRIVER};"
        f"Server=tcp:{AZURE_SQL_SERVER},1433;"
        f"Database={AZURE_SQL_DATABASE};"
        f"Uid={AZURE_SQL_USER};"
        f"Pwd={AZURE_SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    conn = pyodbc.connect(conn_str)

    rows = [parse_booking_for_db(b) for b in all_bookings]
    rows = [r for r in rows if r["booking_number"]]
    inserted = upsert_to_azure_sql(rows, conn)
    conn.close()
    print(f"\nUpserted {inserted} bookings to Azure SQL.")


if __name__ == "__main__":
    main()
