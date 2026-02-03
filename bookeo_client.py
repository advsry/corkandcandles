"""
Bookeo API client for fetching bookings.
API reference: https://www.bookeo.com/apiref/#tag/Bookings
Authentication: apiKey and secretKey as query parameters or headers.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Generator, Iterator

import requests

logger = logging.getLogger(__name__)

BOOKEO_BASE_URL = "https://api.bookeo.com/v2"
MAX_DAYS_PER_CALL = 31
MAX_ITEMS_PER_PAGE = 100


class BookeoAPIError(Exception):
    """Raised when Bookeo API returns an error."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class BookeoClient:
    """Client for Bookeo API v2."""

    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key
        self._session = requests.Session()

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Make authenticated request to Bookeo API."""
        url = f"{BOOKEO_BASE_URL}{path}"
        params = dict(params or {})
        params.setdefault("apiKey", self.api_key)
        params.setdefault("secretKey", self.secret_key)

        resp = self._session.request(method, url, params=params, timeout=60, **kwargs)
        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {}

        if not resp.ok:
            msg = data.get("message", data.get("error", resp.text or resp.reason))
            raise BookeoAPIError(
                f"Bookeo API error: {msg}",
                status_code=resp.status_code,
                response=data,
            )
        return data

    def get_bookings(
        self,
        start_time: datetime,
        end_time: datetime,
        *,
        include_canceled: bool = True,
        expand_customer: bool = True,
        expand_participants: bool = False,
    ) -> Iterator[dict[str, Any]]:
        """
        Retrieve bookings in a time range (max 31 days per API call).
        Yields individual booking objects. Handles pagination automatically.
        """
        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        params = {
            "startTime": start_str,
            "endTime": end_str,
            "includeCanceled": str(include_canceled).lower(),
            "expandCustomer": str(expand_customer).lower(),
            "expandParticipants": str(expand_participants).lower(),
            "itemsPerPage": MAX_ITEMS_PER_PAGE,
        }
        page_token: str | None = None
        page_number = 1

        while True:
            if page_token:
                params["pageNavigationToken"] = page_token
                params["pageNumber"] = page_number
            else:
                params.pop("pageNavigationToken", None)
                params.pop("pageNumber", None)

            data = self._request("GET", "/bookings", params=params)
            info = data.get("info", {})
            bookings = data.get("data", [])

            for b in bookings:
                yield b

            page_token = info.get("pageNavigationToken")
            current_page = info.get("currentPage", 0)
            total_pages = info.get("totalPages", 0)
            if not page_token or not bookings or current_page >= total_pages:
                break
            page_number += 1

    def fetch_all_bookings(
        self,
        historical_start: datetime,
        future_end: datetime,
        *,
        include_canceled: bool = True,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch all bookings from historical_start to future_end in 31-day chunks
        (required by Bookeo API). Yields each booking once.
        """
        current_start = historical_start
        while current_start < future_end:
            chunk_end = min(
                current_start + timedelta(days=MAX_DAYS_PER_CALL),
                future_end,
            )
            logger.info(
                "Fetching bookings %s to %s",
                current_start.date(),
                chunk_end.date(),
            )
            for booking in self.get_bookings(
                current_start,
                chunk_end,
                include_canceled=include_canceled,
            ):
                yield booking
            current_start = chunk_end
