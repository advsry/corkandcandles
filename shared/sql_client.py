"""
Azure SQL client for syncing bookings.
"""
import json
import os
from datetime import datetime
from typing import Any

import pyodbc


def get_connection_string() -> str:
    """Build Azure SQL connection string from environment."""
    server = os.environ.get("AZURE_SQL_SERVER")
    database = os.environ.get("AZURE_SQL_DATABASE")
    user = os.environ.get("AZURE_SQL_USER")
    password = os.environ.get("AZURE_SQL_PASSWORD")
    driver = "{ODBC Driver 18 for SQL Server}"

    if not all([server, database, user, password]):
        raise ValueError(
            "AZURE_SQL_SERVER, AZURE_SQL_DATABASE, AZURE_SQL_USER, "
            "AZURE_SQL_PASSWORD must be set"
        )

    return (
        f"Driver={driver};Server=tcp:{server},1433;Database={database};"
        f"Uid={user};Pwd={password};Encrypt=yes;TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )


def ensure_table(conn: pyodbc.Connection) -> None:
    """Create Bookings table if it does not exist."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Bookings')
        CREATE TABLE Bookings (
            BookingNumber NVARCHAR(64) PRIMARY KEY,
            EventId NVARCHAR(128),
            ProductId NVARCHAR(128),
            ProductName NVARCHAR(256),
            StartTime DATETIME2,
            EndTime DATETIME2,
            CustomerId NVARCHAR(128),
            Title NVARCHAR(512),
            Canceled BIT,
            CancelationTime DATETIME2,
            CreationTime DATETIME2,
            LastChangeTime DATETIME2,
            RawJson NVARCHAR(MAX),
            SyncedAt DATETIME2 DEFAULT GETUTCDATE()
        )
    """)
    conn.commit()


def parse_datetime(val: str | None) -> str | None:
    """Parse RFC 3339 date-time to SQL datetime2 string."""
    if not val:
        return None
    try:
        # Handle format like 2016-12-19T16:39:00-08:00
        dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return val[:19] if val else None


def _booking_values(booking: dict[str, Any]) -> tuple:
    """Extract typed values from booking for SQL."""
    return (
        str(booking.get("bookingNumber") or "")[:64],
        str(booking.get("eventId") or "")[:128],
        str(booking.get("productId") or "")[:128],
        str(booking.get("productName") or "")[:256],
        parse_datetime(booking.get("startTime")),
        parse_datetime(booking.get("endTime")),
        str(booking.get("customerId") or "")[:128],
        str(booking.get("title") or "")[:512],
        bool(booking.get("canceled", False)),
        parse_datetime(booking.get("cancelationTime")),
        parse_datetime(booking.get("creationTime")),
        parse_datetime(booking.get("lastChangeTime")),
        json.dumps(booking),
    )


def upsert_booking(conn: pyodbc.Connection, booking: dict[str, Any]) -> None:
    """Insert or update a single booking."""
    if not booking.get("bookingNumber"):
        return

    vals = _booking_values(booking)
    cursor = conn.cursor()

    cursor.execute("""
        MERGE Bookings AS target
        USING (
            SELECT ? AS BookingNumber, ? AS EventId, ? AS ProductId, ? AS ProductName,
                   ? AS StartTime, ? AS EndTime, ? AS CustomerId, ? AS Title,
                   ? AS Canceled, ? AS CancelationTime, ? AS CreationTime,
                   ? AS LastChangeTime, ? AS RawJson
        ) AS source
        ON target.BookingNumber = source.BookingNumber
        WHEN MATCHED THEN UPDATE SET
            EventId = source.EventId,
            ProductId = source.ProductId,
            ProductName = source.ProductName,
            StartTime = source.StartTime,
            EndTime = source.EndTime,
            CustomerId = source.CustomerId,
            Title = source.Title,
            Canceled = source.Canceled,
            CancelationTime = source.CancelationTime,
            CreationTime = source.CreationTime,
            LastChangeTime = source.LastChangeTime,
            RawJson = source.RawJson,
            SyncedAt = GETUTCDATE()
        WHEN NOT MATCHED THEN INSERT (
            BookingNumber, EventId, ProductId, ProductName, StartTime, EndTime,
            CustomerId, Title, Canceled, CancelationTime, CreationTime,
            LastChangeTime, RawJson
        ) VALUES (
            source.BookingNumber, source.EventId, source.ProductId, source.ProductName,
            source.StartTime, source.EndTime, source.CustomerId, source.Title,
            source.Canceled, source.CancelationTime, source.CreationTime,
            source.LastChangeTime, source.RawJson
        );
    """, vals)
    conn.commit()


def sync_bookings_to_sql(bookings: list[dict[str, Any]]) -> int:
    """
    Sync a list of bookings to Azure SQL. Returns count of upserted rows.
    """
    conn_str = get_connection_string()
    with pyodbc.connect(conn_str) as conn:
        ensure_table(conn)
        for b in bookings:
            upsert_booking(conn, b)
        return len(bookings)
