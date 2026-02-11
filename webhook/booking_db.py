"""
Booking database logic for webhook (shared with scripts/booking_db.py).
"""

import json
import os
from typing import Any, Dict

AZURE_SQL_DRIVER = "{ODBC Driver 18 for SQL Server}"


def get_connection():
    """Create and return a pyodbc connection to Azure SQL."""
    import pyodbc

    conn_str = (
        f"Driver={AZURE_SQL_DRIVER};"
        f"Server=tcp:{os.getenv('AZURE_SQL_SERVER')},1433;"
        f"Database={os.getenv('AZURE_SQL_DATABASE', 'corkandcandles-bookings')};"
        f"Uid={os.getenv('AZURE_SQL_USER')};"
        f"Pwd={os.getenv('AZURE_SQL_PASSWORD')};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def parse_booking_for_db(booking: Dict[str, Any]) -> Dict[str, Any]:
    """Extract fields for database insert from Bookeo API booking JSON."""
    participants = booking.get("participants", {})
    numbers = participants.get("numbers", [])
    total_participants = sum(n.get("number", 0) for n in numbers)

    price = booking.get("price", {})
    total_gross = price.get("totalGross", {}).get("amount")
    total_net = price.get("totalNet", {}).get("amount")
    total_paid = price.get("totalPaid", {}).get("amount")
    currency = price.get("totalGross", {}).get("currency")

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
        "last_change_time": booking.get("lastChangeTime"),
        "last_change_agent": booking.get("lastChangeAgent"),
        "total_participants": total_participants,
        "total_gross": str(total_gross) if total_gross is not None else None,
        "total_net": str(total_net) if total_net is not None else None,
        "total_paid": str(total_paid) if total_paid is not None else None,
        "currency": currency,
        "raw_json": json.dumps(booking) if booking else None,
    }


def create_bookings_table_if_not_exists(conn) -> None:
    """Create the Bookings table in the database if it does not exist."""
    cursor = conn.cursor()
    cursor.execute("""
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'Bookings')
        BEGIN
            CREATE TABLE Bookings (
                booking_number NVARCHAR(50) PRIMARY KEY,
                event_id NVARCHAR(100),
                start_time DATETIMEOFFSET NOT NULL,
                end_time DATETIMEOFFSET,
                customer_id NVARCHAR(50),
                title NVARCHAR(255),
                product_name NVARCHAR(500),
                product_id NVARCHAR(50),
                canceled BIT NOT NULL DEFAULT 0,
                accepted BIT NOT NULL DEFAULT 1,
                no_show BIT NOT NULL DEFAULT 0,
                private_event BIT NOT NULL DEFAULT 0,
                source_ip NVARCHAR(45),
                creation_time DATETIMEOFFSET,
                last_change_time DATETIMEOFFSET,
                last_change_agent NVARCHAR(255),
                total_participants INT,
                total_gross NVARCHAR(20),
                total_net NVARCHAR(20),
                total_paid NVARCHAR(20),
                currency NVARCHAR(10),
                raw_json NVARCHAR(MAX),
                created_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET(),
                updated_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET()
            );
            CREATE INDEX IX_Bookings_StartTime ON Bookings(start_time);
            CREATE INDEX IX_Bookings_CustomerId ON Bookings(customer_id);
            CREATE INDEX IX_Bookings_ProductId ON Bookings(product_id);
            CREATE INDEX IX_Bookings_Canceled ON Bookings(canceled);
        END
    """)
    conn.commit()
    cursor.close()


def upsert_booking(conn, row: Dict[str, Any]) -> bool:
    """Insert or update a single booking."""
    if not row.get("booking_number"):
        return False

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
    params = (
        row["event_id"], row["start_time"], row["end_time"], row["customer_id"], row["title"],
        row["product_name"], row["product_id"], row["canceled"], row["accepted"], row["no_show"],
        row["private_event"], row["source_ip"], row["creation_time"], row["last_change_time"],
        row["last_change_agent"], row["total_participants"], row["total_gross"], row["total_net"],
        row["total_paid"], row["currency"], row["raw_json"], row["booking_number"],
    )
    cursor.execute(update_sql, params)
    if cursor.rowcount == 0:
        cursor.execute(
            insert_sql,
            (
                row["booking_number"], row["event_id"], row["start_time"], row["end_time"],
                row["customer_id"], row["title"], row["product_name"], row["product_id"],
                row["canceled"], row["accepted"], row["no_show"], row["private_event"],
                row["source_ip"], row["creation_time"], row["last_change_time"],
                row["last_change_agent"], row["total_participants"], row["total_gross"],
                row["total_net"], row["total_paid"], row["currency"], row["raw_json"],
            ),
        )
    conn.commit()
    cursor.close()
    return True
