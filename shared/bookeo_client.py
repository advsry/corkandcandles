"""
Bookeo API client for fetching bookings.
API Reference: https://www.bookeo.com/apiref/#tag/Bookings
"""
import os
from datetime import datetime, timedelta
from typing import Any

import requests

BOOKEO_BASE_URL = "https://api.bookeo.com/v2"


def get_auth_headers() -> dict[str, str]:
    """Return headers with Bookeo API credentials."""
    api_key = os.environ.get("BOOKEO_API_KEY")
    secret_key = os.environ.get("BOOKEO_SECRET_KEY")
    if not api_key or not secret_key:
        raise ValueError("BOOKEO_API_KEY and BOOKEO_SECRET_KEY must be set")
    return {
        "X-Bookeo-apiKey": api_key,
        "X-Bookeo-secretKey": secret_key,
        "Content-Type": "application/json",
    }


def fetch_bookings(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    last_updated_start: datetime | None = None,
    last_updated_end: datetime | None = None,
    product_id: str | None = None,
    include_canceled: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetch all bookings from Bookeo API with pagination.
    Uses lastUpdated filter by default to get recent bookings (last 31 days).
    """
    bookings: list[dict[str, Any]] = []
    page_token: str | None = None
    page_num = 1

    # Default to last 31 days if no time range specified
    if not start_time and not last_updated_start:
        now = datetime.utcnow()
        last_updated_start = now - timedelta(days=31)
        last_updated_end = now

    while True:
        params: dict[str, Any] = {
            "itemsPerPage": 100,
            "pageNumber": page_num,
        }
        if start_time and end_time:
            params["startTime"] = start_time.strftime("%Y-%m-%dT%H:%M:%S-00:00")
            params["endTime"] = end_time.strftime("%Y-%m-%dT%H:%M:%S-00:00")
        if last_updated_start and last_updated_end:
            params["lastUpdatedStartTime"] = last_updated_start.strftime(
                "%Y-%m-%dT%H:%M:%S-00:00"
            )
            params["lastUpdatedEndTime"] = last_updated_end.strftime(
                "%Y-%m-%dT%H:%M:%S-00:00"
            )
        if product_id:
            params["productId"] = product_id
        params["includeCanceled"] = str(include_canceled).lower()

        if page_token:
            params["pageNavigationToken"] = page_token

        resp = requests.get(
            f"{BOOKEO_BASE_URL}/bookings",
            headers=get_auth_headers(),
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        bookings.extend(data.get("data", []))
        info = data.get("info", {})
        page_token = info.get("pageNavigationToken")

        if not page_token:
            break
        page_num += 1

    return bookings


def fetch_bookings_by_date_range(
    days_back: int = 365,
    days_forward: int = 365,
) -> list[dict[str, Any]]:
    """
    Fetch bookings by start time range. Useful for full sync.
    Bookeo allows max 31 days per request, so we chunk into 31-day windows.
    """
    all_bookings: list[dict[str, Any]] = []
    now = datetime.utcnow()
    start = now - timedelta(days=days_back)
    end = now + timedelta(days=days_forward)

    current_start = start
    while current_start < end:
        current_end = min(current_start + timedelta(days=31), end)
        chunk = fetch_bookings(
            start_time=current_start,
            end_time=current_end,
        )
        all_bookings.extend(chunk)
        current_start = current_end

    # Deduplicate by bookingNumber
    seen = set()
    unique = []
    for b in all_bookings:
        bn = b.get("bookingNumber")
        if bn and bn not in seen:
            seen.add(bn)
            unique.append(b)

    return unique
