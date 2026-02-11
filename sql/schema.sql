-- Bookeo Bookings Schema for Azure SQL Database
-- Run this after database is created

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

    PRINT 'Table Bookings created successfully.';
END
ELSE
BEGIN
    PRINT 'Table Bookings already exists.';
END

-- SyncState: tracks last sync time for incremental Bookeo sync
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'SyncState')
BEGIN
    CREATE TABLE SyncState (
        sync_key NVARCHAR(50) PRIMARY KEY,
        last_sync_time DATETIMEOFFSET NOT NULL,
        updated_at DATETIMEOFFSET DEFAULT SYSDATETIMEOFFSET()
    );
    PRINT 'Table SyncState created successfully.';
END
