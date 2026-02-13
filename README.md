# Cork and Candles – Bookeo to Azure SQL Sync

Python-based Azure Function App that syncs bookings from the Bookeo API (Cork and Candles Center City) into Azure SQL Database, with webhook support for real-time updates.

## Features

- **Webhook trigger**: Receives Bookeo webhooks when new bookings are created; queues a sync job
- **Queue processor**: Syncs bookings from Bookeo to Azure SQL when webhook fires
- **Daily sync**: Timer-triggered full sync at 2 AM UTC
- **Manual sync**: HTTP endpoint to trigger sync on demand

## Prerequisites

- Python 3.10 or 3.11
- Azure Functions Core Tools v4
- [ODBC Driver 18 for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) (Linux: `apt-get install msodbcsql18`)
- Azure Storage account (for queue)

## Local Setup

1. Copy `local.settings.json.example` to `local.settings.json`
2. Fill in values:
   - `BOOKEO_API_KEY`, `BOOKEO_SECRET_KEY` – from Bookeo
   - `AZURE_SQL_*` – your Azure SQL connection details
   - `AzureWebJobsStorage` – connection string for Azure Storage (or `UseDevelopmentStorage=true` with Azurite)

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Run locally:

   ```bash
   func start
   ```

## Deploy to Azure (Linux Function App)

### Option A: Standard deployment (may need custom image for pyodbc)

```bash
az functionapp create \
  --resource-group <your-rg> \
  --consumption-plan-location westus2 \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name corkandcandles-sync \
  --storage-account <your-storage> \
  --os-type Linux

func azure functionapp publish corkandcandles-sync
```

### Option B: Custom Docker image (recommended – includes ODBC driver for Azure SQL)

Uses Docker buildx for BuildKit-backed builds (better caching, multi-platform support).

```bash
# Build and push to Azure Container Registry (via buildx)
az acr create --resource-group <your-rg> --name corkandcandlesacr --sku Basic
az acr login --name corkandcandlesacr

# Ensure buildx is available (default in Docker Desktop)
docker buildx build --platform linux/amd64 \
  -t corkandcandlesacr.azurecr.io/bookeo-sync:v1 \
  --push .

# Or use the convenience script:
# ./scripts/build.sh v1

# Create Function App from container
az functionapp create \
  --resource-group <your-rg> \
  --consumption-plan-location westus2 \
  --name corkandcandles-sync \
  --storage-account <your-storage> \
  --functions-version 4 \
  --os-type Linux \
  --runtime python \
  --runtime-version 3.11 \
  --image corkandcandlesacr.azurecr.io/bookeo-sync:v1 \
  --registry-login-server corkandcandlesacr.azurecr.io \
  --registry-username <acr-username> \
  --registry-password <acr-password>
```

## Application Settings (Azure)

Configure these in the Function App → Configuration → Application settings:

| Setting | Description |
|--------|-------------|
| `BOOKEO_API_KEY` | Bookeo API key |
| `BOOKEO_SECRET_KEY` | Bookeo secret key |
| `AZURE_SQL_SERVER` | e.g. `corkandcandles.database.windows.net` |
| `AZURE_SQL_DATABASE` | e.g. `cc-bookings` |
| `AZURE_SQL_USER` | SQL username |
| `AZURE_SQL_PASSWORD` | SQL password |
| `BOOKEO_WEBHOOK_URL` | Full webhook URL for signature verification (e.g. `https://corkandcandles-sync.azurewebsites.net/api/bookeo-webhook`) |

## Register Bookeo Webhook

After deploying, register the webhook with Bookeo:

```bash
export BOOKEO_API_KEY="..."
export BOOKEO_SECRET_KEY="..."

python scripts/register_webhook.py --url "https://YOUR-APP.azurewebsites.net/api/bookeo-webhook"
```

List existing webhooks:

```bash
python scripts/register_webhook.py --list
```

## Database

The `Bookings` table is created automatically on the first sync. To create it manually, run `sql/schema.sql` against your Azure SQL database.

## Endpoints

| Route | Method | Auth | Description |
|-------|--------|------|-------------|
| `/api/bookeo-webhook` | POST | None | Bookeo webhook (receives events, queues sync) |
| `/api/sync` | GET/POST | Function key | Manual sync trigger |

## Security Note

**Do not commit** `local.settings.json` or `.env` with real credentials. They are listed in `.gitignore`.
