#!/usr/bin/env python3
"""
Export bookings from Azure SQL Database to an Excel file.
Reads from the Bookings table and writes to .xlsx format.
"""

import os
import sys
import argparse
from datetime import datetime

import pandas as pd
import openpyxl.utils
from dotenv import load_dotenv

load_dotenv()

# Azure SQL config (same as load_bookeo_bookings.py)
AZURE_SQL_SERVER = os.getenv("AZURE_SQL_SERVER")
AZURE_SQL_DATABASE = os.getenv("AZURE_SQL_DATABASE", "corkandcandles-bookings")
AZURE_SQL_USER = os.getenv("AZURE_SQL_USER")
AZURE_SQL_PASSWORD = os.getenv("AZURE_SQL_PASSWORD")
AZURE_SQL_DRIVER = "{ODBC Driver 18 for SQL Server}"


def get_connection():
    """Create and return a pyodbc connection to Azure SQL."""
    if not all([AZURE_SQL_SERVER, AZURE_SQL_USER, AZURE_SQL_PASSWORD]):
        print(
            "Azure SQL credentials not set. Set AZURE_SQL_SERVER, AZURE_SQL_USER, AZURE_SQL_PASSWORD.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        import pyodbc
    except ImportError:
        print("Install pyodbc: pip install pyodbc", file=sys.stderr)
        sys.exit(1)
    conn_str = (
        f"Driver={AZURE_SQL_DRIVER};"
        f"Server=tcp:{AZURE_SQL_SERVER},1433;"
        f"Database={AZURE_SQL_DATABASE};"
        f"Uid={AZURE_SQL_USER};"
        f"Pwd={AZURE_SQL_PASSWORD};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    return pyodbc.connect(conn_str)


def fetch_bookings(conn, include_canceled: bool = True) -> pd.DataFrame:
    """Fetch all bookings from the database into a pandas DataFrame."""
    query = "SELECT * FROM Bookings"
    if not include_canceled:
        query += " WHERE canceled = 0"
    query += " ORDER BY start_time"

    df = pd.read_sql(query, conn)

    # Exclude raw_json from Excel output (too large, not human-readable)
    if "raw_json" in df.columns:
        df = df.drop(columns=["raw_json"])
    return df


def export_to_excel(df: pd.DataFrame, output_path: str) -> None:
    """Write DataFrame to Excel with formatted columns."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Bookings", index=False)
        worksheet = writer.sheets["Bookings"]
        # Auto-adjust column widths
        for col_idx, column in enumerate(df.columns, 1):
            max_length = max(
                df[column].astype(str).map(len).max() if len(df) > 0 else 0,
                len(str(column)),
            )
            worksheet.column_dimensions[
                openpyxl.utils.get_column_letter(col_idx)
            ].width = min(max_length + 2, 50)


def main():
    parser = argparse.ArgumentParser(description="Export bookings from Azure SQL to Excel")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=f"bookings_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        help="Output Excel file path (default: bookings_export_YYYYMMDD_HHMMSS.xlsx)",
    )
    parser.add_argument(
        "--include-canceled",
        action="store_true",
        default=True,
        help="Include canceled bookings (default: True)",
    )
    parser.add_argument(
        "--exclude-canceled",
        action="store_false",
        dest="include_canceled",
        help="Exclude canceled bookings from export",
    )
    args = parser.parse_args()

    print("Connecting to Azure SQL...")
    conn = get_connection()

    print("Fetching bookings...")
    df = fetch_bookings(conn, include_canceled=args.include_canceled)
    conn.close()

    if df.empty:
        print("No bookings found.")
        return

    print(f"Exporting {len(df)} bookings to {args.output}...")
    export_to_excel(df, args.output)
    print(f"Done. Exported to {args.output}")


if __name__ == "__main__":
    main()
