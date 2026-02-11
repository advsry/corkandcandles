#!/bin/bash
# Run incremental Bookeo sync. Call from cron every hour.
# Example crontab: 0 * * * * /path/to/corkandcandles/scripts/sync_hourly.sh >> /var/log/bookeo-sync.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

cd "$PROJECT_ROOT"
exec python3 scripts/load_bookeo_bookings.py --incremental
