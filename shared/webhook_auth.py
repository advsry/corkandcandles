"""
Bookeo webhook signature verification.
See: https://bookeo.com/api/webhooks
"""
import hashlib
import hmac
import os
import time


def verify_bookeo_signature(
    body: bytes,
    timestamp_header: str,
    message_id_header: str,
    signature_header: str,
    webhook_url: str,
    secret_key: str,
    tolerance_seconds: int = 120,
) -> bool:
    """
    Verify that a webhook request originated from Bookeo.
    Returns True if valid, False otherwise.
    """
    if not all([timestamp_header, message_id_header, signature_header]):
        return False

    try:
        ts = int(timestamp_header)
        now_ms = int(time.time() * 1000)
        if abs(now_ms - ts) > tolerance_seconds * 1000:
            return False
    except ValueError:
        return False

    hashing_message = (
        timestamp_header + message_id_header + webhook_url + body.decode("utf-8")
    )
    expected = hmac.new(
        secret_key.encode("utf-8"),
        hashing_message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, signature_header)
