#!/usr/bin/env python3
"""
Register the Bookeo webhook for new booking notifications.
Run this AFTER deploying the Azure Function App to get your webhook URL.

Usage:
    python register_webhook.py --url "https://YOUR-APP.azurewebsites.net/api/bookeo-webhook"
"""
import argparse
import os
import sys

import requests

# Add parent for shared imports when run from scripts/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from shared.bookeo_client import get_auth_headers
except ImportError:
    # Fallback if running from project root
    sys.path.insert(0, os.path.dirname(__file__))
    from shared.bookeo_client import get_auth_headers


def register_webhook(webhook_url: str) -> dict:
    """Register webhook with Bookeo for domain=bookings, type=created."""
    resp = requests.post(
        "https://api.bookeo.com/v2/webhooks",
        headers={**get_auth_headers(), "Content-Type": "application/json"},
        json={
            "url": webhook_url,
            "domain": "bookings",
            "type": "created",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def list_webhooks() -> dict:
    """List existing webhooks."""
    resp = requests.get(
        "https://api.bookeo.com/v2/webhooks",
        headers=get_auth_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Register Bookeo webhook")
    parser.add_argument(
        "--url",
        required=True,
        help="Full webhook URL (e.g. https://xxx.azurewebsites.net/api/bookeo-webhook)",
    )
    parser.add_argument("--list", action="store_true", help="List existing webhooks")
    args = parser.parse_args()

    if args.list:
        data = list_webhooks()
        print("Existing webhooks:", data)
        return

    if not args.url.startswith("https://"):
        print("Error: Webhook URL must use HTTPS")
        sys.exit(1)

    result = register_webhook(args.url.rstrip("/"))
    print("Webhook registered successfully:", result)
    print("\nSet BOOKEO_WEBHOOK_URL in your Function App settings to:", args.url)


if __name__ == "__main__":
    main()
