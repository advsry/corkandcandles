-- Bookings table for Cork and Candles Center City
-- Run this manually if the table is not auto-created on first sync

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
);

-- Optional: index for common queries
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Bookings_StartTime')
CREATE INDEX IX_Bookings_StartTime ON Bookings (StartTime);

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_Bookings_Canceled')
CREATE INDEX IX_Bookings_Canceled ON Bookings (Canceled);
