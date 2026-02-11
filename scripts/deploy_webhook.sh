#!/bin/bash
# Deploy Bookeo webhook Function App to Azure (Linux with custom Docker image)
# Prerequisites: Azure CLI, database already deployed
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RESOURCE_GROUP="${RESOURCE_GROUP:-CandC_Franchisor}"
LOCATION="${LOCATION:-westus2}"
BASE_NAME="${BASE_NAME:-corkandcandles}"
SQL_SERVER_FQDN="${SQL_SERVER_FQDN:-corkandcandles.database.windows.net}"
SQL_DATABASE_NAME="${SQL_DATABASE_NAME:-corkandcandles-bookings}"
# ACR name must match Bicep: take(replace(baseName,'-','') + 'acr', 24)
ACR_NAME="${ACR_NAME:-$(echo "$BASE_NAME" | tr -d '-')acr}"

echo "=== Deploying Bookeo Webhook Function App (Linux) ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "Function App: ${BASE_NAME}-webhook"
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Load .env for Bookeo keys
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
fi

if [ -z "$BOOKEO_SECRET_KEY" ]; then
    echo "BOOKEO_SECRET_KEY not set. Add to .env or export."
    exit 1
fi

# Prompt for SQL password if not in env
if [ -z "$AZURE_SQL_PASSWORD" ]; then
    read -sp "SQL admin password: " AZURE_SQL_PASSWORD
    echo ""
fi
SQL_ADMIN="${AZURE_SQL_USER:-sqladmin}"

# Webhook URL (known after deploy; we use expected hostname)
WEBHOOK_URL="https://${BASE_NAME}-webhook.azurewebsites.net/api/bookeo"

echo "Deploying Function App infrastructure (ACR, Linux Function App)..."
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --name "bookeo-webhook-deploy" \
    --template-file "$PROJECT_ROOT/azure/function-app.bicep" \
    --parameters baseName="$BASE_NAME" \
        location="$LOCATION" \
        sqlServerFqdn="$SQL_SERVER_FQDN" \
        sqlDatabaseName="$SQL_DATABASE_NAME" \
        sqlAdminLogin="$SQL_ADMIN" \
        sqlAdminPassword="$AZURE_SQL_PASSWORD" \
        bookeoSecretKey="$BOOKEO_SECRET_KEY" \
        webhookUrl="$WEBHOOK_URL" \
    --output none

echo ""
echo "Building and pushing Docker image to ACR..."
cd "$PROJECT_ROOT/webhook"
az acr build --registry "$ACR_NAME" --image webhook:latest .

echo ""
echo "Restarting Function App to pull new image..."
az functionapp restart --resource-group "$RESOURCE_GROUP" --name "${BASE_NAME}-webhook"

echo ""
echo "=== Webhook deployed! ==="
echo "Webhook URL: $WEBHOOK_URL"
echo ""
echo "Register with Bookeo:"
echo "  python scripts/register_webhook.py $WEBHOOK_URL"
echo ""
echo "Or check existing webhooks:"
echo "  python scripts/register_webhook.py --list"
