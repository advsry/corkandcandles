"""
Cork and Candles - Bookeo to Azure SQL Sync
Azure Function App with webhook trigger for new bookings.
"""
import logging
import os
from datetime import datetime, timedelta

import azure.functions as func

from shared.bookeo_client import fetch_bookings_by_date_range, fetch_bookings
from shared.sql_client import sync_bookings_to_sql
from shared.webhook_auth import verify_bookeo_signature

app = func.FunctionApp()


@app.route(route="bookeo-webhook", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
@app.queue_output(
    arg_name="sync_queue",
    queue_name="bookeo-sync-queue",
    connection="AzureWebJobsStorage",
)
def bookeo_webhook(req: func.HttpRequest, sync_queue: func.Out[str]) -> func.HttpResponse:
    """
    Receives Bookeo webhook notifications for new/updated bookings.
    Validates signature, queues sync job, returns 200 within 5 seconds.
    """
    body = req.get_body()
    if not body:
        return func.HttpResponse("Bad Request", status_code=400)

    secret_key = os.environ.get("BOOKEO_SECRET_KEY")
    webhook_url = os.environ.get("BOOKEO_WEBHOOK_URL", "").rstrip("/")
    if not webhook_url and req.url:
        webhook_url = req.url.split("?")[0]

    timestamp = req.headers.get("X-Bookeo-Timestamp", "")
    message_id = req.headers.get("X-Bookeo-MessageId", "")
    signature = req.headers.get("X-Bookeo-Signature", "")

    if secret_key and webhook_url and signature:
        if not verify_bookeo_signature(
            body, timestamp, message_id, signature, webhook_url, secret_key
        ):
            logging.warning("Webhook signature verification failed")
            return func.HttpResponse("Forbidden", status_code=403)

    sync_queue.set("sync")
    return func.HttpResponse("OK", status_code=200)


@app.queue_trigger(
    arg_name="msg",
    queue_name="bookeo-sync-queue",
    connection="AzureWebJobsStorage",
)
def process_sync_queue(msg: func.QueueMessage) -> None:
    """
    Processes sync requests from the queue. Fetches fresh data from Bookeo
    and updates Azure SQL. Triggered by webhook or manual sync.
    """
    logging.info("Processing sync from queue: %s", msg.get_body().decode())
    run_sync()


@app.timer_trigger(schedule="0 0 2 * * *", arg_name="timer")  # 2 AM UTC daily
def daily_sync(timer: func.TimerRequest) -> None:
    """Daily full sync of bookings from Bookeo to Azure SQL."""
    logging.info("Running scheduled daily sync")
    run_sync()


@app.route(route="sync", methods=["POST", "GET"], auth_level=func.AuthLevel.FUNCTION)
def manual_sync(req: func.HttpRequest) -> func.HttpResponse:
    """
    Manual trigger for sync. POST or GET to /api/sync.
    Requires function key (auth_level=FUNCTION).
    """
    run_sync()
    return func.HttpResponse(
        '{"status": "ok", "message": "Sync completed"}',
        status_code=200,
        mimetype="application/json",
    )


def run_sync() -> None:
    """Fetch bookings from Bookeo and sync to Azure SQL."""
    try:
        bookings = fetch_bookings_by_date_range(days_back=365, days_forward=365)
        count = sync_bookings_to_sql(bookings)
        logging.info("Synced %d bookings to Azure SQL", count)
    except Exception as e:
        logging.exception("Sync failed: %s", e)
        raise
