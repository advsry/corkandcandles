"""
Azure Function: Bookeo webhook receiver.
Updates SQL database when a new booking is created or updated in Bookeo.
"""

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path

import azure.functions as func

# Prefer local scripts/booking_db when running from project root (e.g. func start)
_project_root = Path(__file__).resolve().parent.parent
_scripts_db = _project_root / "scripts" / "booking_db.py"
if _scripts_db.exists():
    sys.path.insert(0, str(_project_root / "scripts"))

from booking_db import (
    create_bookings_table_if_not_exists,
    get_connection,
    parse_booking_for_db,
    upsert_booking,
)

app = func.FunctionApp()


def verify_bookeo_signature(
    body: bytes,
    timestamp_header: str,
    message_id_header: str,
    signature_header: str,
    webhook_url: str,
    secret_key: str,
) -> bool:
    """Verify webhook message authenticity using HMAC-SHA256."""
    if not all([body, timestamp_header, message_id_header, signature_header, webhook_url, secret_key]):
        return False
    try:
        # Check timestamp is within 120 seconds
        ts_ms = int(timestamp_header)
        now_ms = int(time.time() * 1000)
        if abs(now_ms - ts_ms) > 120_000:
            return False
        # Build hashing message: timestamp + messageId + url + body
        body_str = body.decode("utf-8") if isinstance(body, bytes) else body
        hashing_message = f"{timestamp_header}{message_id_header}{webhook_url}{body_str}"
        expected = hmac.new(
            secret_key.encode("utf-8"),
            hashing_message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
    except (ValueError, TypeError):
        return False


@app.route(route="bookeo", methods=["POST"])
def bookeo_webhook(req: func.HttpRequest) -> func.HttpResponse:
    """
    Receive Bookeo webhook notifications for booking created/updated.
    Must return 2xx within 5 seconds or Bookeo will retry.
    """
    # Load config from environment (Azure App Settings)
    secret_key = os.getenv("BOOKEO_SECRET_KEY")
    webhook_url = os.getenv("BOOKEO_WEBHOOK_URL")

    if not secret_key or not webhook_url:
        return func.HttpResponse(
            "Server misconfigured: BOOKEO_SECRET_KEY or BOOKEO_WEBHOOK_URL not set",
            status_code=500,
        )

    # Verify signature
    body = req.get_body()
    timestamp = req.headers.get("X-Bookeo-Timestamp", "")
    message_id = req.headers.get("X-Bookeo-MessageId", "")
    signature = req.headers.get("X-Bookeo-Signature", "")

    if not verify_bookeo_signature(body, timestamp, message_id, signature, webhook_url, secret_key):
        return func.HttpResponse("Invalid signature", status_code=401)

    # Parse payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return func.HttpResponse("Invalid JSON", status_code=400)

    item = payload.get("item")
    if not item:
        return func.HttpResponse("Missing item in payload", status_code=400)

    # Upsert to database
    try:
        conn = get_connection()
        create_bookings_table_if_not_exists(conn)
        row = parse_booking_for_db(item)
        upsert_booking(conn, row)
        conn.close()
    except Exception as e:
        return func.HttpResponse(f"Database error: {str(e)}", status_code=500)

    return func.HttpResponse("OK", status_code=200)
