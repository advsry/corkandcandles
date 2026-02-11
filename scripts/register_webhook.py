#!/usr/bin/env python3
"""
Register Bookeo webhooks to receive real-time booking notifications.
Registers webhooks for domain=bookings, types=created and updated.
Run once after deploying the webhook endpoint.
"""

import os
import sys
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

BOOKEO_BASE_URL = "https://api.bookeo.com/v2"
BOOKEO_API_KEY = os.getenv("BOOKEO_API_KEY")
BOOKEO_SECRET_KEY = os.getenv("BOOKEO_SECRET_KEY")


def register_webhook(webhook_url: str, domain: str, event_type: str) -> dict:
    """Register a webhook with Bookeo. Returns API response."""
    params = {
        "apiKey": BOOKEO_API_KEY,
        "secretKey": BOOKEO_SECRET_KEY,
    }
    body = {
        "domain": domain,
        "type": event_type,
        "url": webhook_url,
    }
    resp = requests.post(
        f"{BOOKEO_BASE_URL}/webhooks",
        params=params,
        json=body,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def list_webhooks() -> list:
    """List current webhooks for the API key."""
    params = {
        "apiKey": BOOKEO_API_KEY,
        "secretKey": BOOKEO_SECRET_KEY,
    }
    resp = requests.get(
        f"{BOOKEO_BASE_URL}/webhooks",
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Register Bookeo webhooks")
    parser.add_argument(
        "webhook_url",
        nargs="?",
        help="HTTPS URL of the webhook endpoint (e.g. https://myapp.azurewebsites.net/api/bookeo)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing webhooks instead of registering",
    )
    args = parser.parse_args()

    if not BOOKEO_API_KEY or not BOOKEO_SECRET_KEY:
        print("Set BOOKEO_API_KEY and BOOKEO_SECRET_KEY in .env", file=sys.stderr)
        sys.exit(1)

    if args.list:
        try:
            webhooks = list_webhooks()
            print(f"Registered webhooks ({len(webhooks)}):")
            for w in webhooks:
                print(f"  - {w.get('domain')}/{w.get('type')}: {w.get('url')}")
        except requests.RequestException as e:
            print(f"API error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if not args.webhook_url:
        print("Provide webhook_url or use --list", file=sys.stderr)
        sys.exit(1)

    url = args.webhook_url.rstrip("/")
    if not url.startswith("https://"):
        print("Webhook URL must use HTTPS", file=sys.stderr)
        sys.exit(1)

    print(f"Registering webhooks for {url}...")
    for event_type in ("created", "updated"):
        try:
            result = register_webhook(url, "bookings", event_type)
            print(f"  Registered bookings/{event_type}: OK")
        except requests.HTTPError as e:
            if e.response.status_code == 409:
                print(f"  bookings/{event_type}: already registered (409)")
            else:
                print(f"  bookings/{event_type}: {e}", file=sys.stderr)
                raise
    print("Done. Set BOOKEO_WEBHOOK_URL to this exact URL in your Function App settings.")


if __name__ == "__main__":
    main()
