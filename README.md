# Cork & Candles – Bookeo Bookings Azure Database

Loads [Bookeo](https://www.bookeo.com) bookings into an Azure SQL Database for each month starting January 1, 2026.

## Prerequisites

- [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli) (for deployment)
- Python 3.10+
- [ODBC Driver 18 for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) (for pyodbc)
- Bookeo API key and secret (from your Bookeo account)

## Quick Start

### 1. Deploy Azure infrastructure

```bash
# Copy env template
cp .env.example .env

# Edit .env with your Bookeo API keys (optional – script has defaults for testing)

# Deploy Azure SQL
./scripts/deploy_azure.sh
```

Follow prompts to deploy the database to the existing SQL server (corkandcandles.database.windows.net, West US 2). The script will output connection values for `.env`.

### 2. Configure environment

Add the Azure SQL connection details to `.env`:

```env
AZURE_SQL_SERVER=corkandcandles.database.windows.net
AZURE_SQL_DATABASE=corkandcandles-bookings
AZURE_SQL_USER=sqladmin
AZURE_SQL_PASSWORD=your_password

BOOKEO_API_KEY=your_api_key
BOOKEO_SECRET_KEY=your_secret_key
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Load bookings

```bash
# Fetch all months starting Jan 2026 (default 24 months) and load to Azure SQL
python scripts/load_bookeo_bookings.py --months 24
```

**Note:** If the existing SQL server is in a different resource group, set `SQL_SERVER_RG` before running the deploy script (e.g. `SQL_SERVER_RG=YourServerRG ./scripts/deploy_azure.sh`).

## Script options

| Option          | Description                                              |
| --------------- | -------------------------------------------------------- |
| `--months N`    | Number of months to fetch (default: 24)                  |
| `--fetch-only`  | Only call the Bookeo API, do not write to the database   |
| `--output FILE` | Save API response as JSON instead of loading to database |

## Manual deployment

If you prefer not to use the deploy script (uses existing SQL server corkandcandles.database.windows.net in West US 2):

```bash
# Deploy database to existing server (ensure server exists in CandC_Franchisor)
az deployment group create \
  --resource-group CandC_Franchisor \
  --template-file azure/main.bicep \
  --parameters sqlServerName=corkandcandles sqlAdminLogin=sqladmin sqlAdminPassword=<password>

# Run schema
sqlcmd -S corkandcandles.database.windows.net -d corkandcandles-bookings \
  -U sqladmin -P <password> -i sql/schema.sql
```

## Project structure

```
├── azure/
│   └── main.bicep          # Database on existing SQL Server
├── sql/
│   └── schema.sql          # Bookings table schema
├── scripts/
│   ├── deploy_azure.sh     # One-click deploy
│   └── load_bookeo_bookings.py  # Fetch + load script
├── .env.example
├── requirements.txt
└── README.md
```

## Database schema

The `Bookings` table stores:

- Core fields: `booking_number`, `event_id`, `start_time`, `end_time`, `customer_id`, `title`
- Product: `product_name`, `product_id`
- Status: `canceled`, `accepted`, `no_show`, `private_event`
- Metadata: `creation_time`, `last_change_time`, `source_ip`
- Pricing: `total_gross`, `total_net`, `total_paid`, `currency`
- Raw JSON for full API response

## Security notes

- Do not commit `.env` (already in `.gitignore`)
- Store Bookeo and Azure credentials in environment variables or a secrets manager
- Consider using Azure Key Vault for production
- The firewall rule `AllowAzureServices` (0.0.0.0–0.0.0.0) enables Azure services only
