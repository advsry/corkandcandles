#!/bin/bash
# Deploy Azure SQL infrastructure and run schema + data load
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RESOURCE_GROUP="${RESOURCE_GROUP:-corkandcandles-rg}"
LOCATION="${LOCATION:-vnet-eastus-bastion}"
BASE_NAME="${BASE_NAME:-corkandcandles}"
SQL_ADMIN="${SQL_ADMIN:-sqladmin}"

echo "=== Deploying Azure SQL for Bookeo Bookings ==="
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login if needed
az account show &> /dev/null || az login

# Create resource group
echo "Creating resource group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# Prompt for password
read -sp "SQL admin password (min 8 chars, upper, lower, number, special): " SQL_PASSWORD
echo ""
if [ ${#SQL_PASSWORD} -lt 8 ]; then
    echo "Password must be at least 8 characters"
    exit 1
fi

# Deploy Bicep
echo "Deploying Bicep template..."
az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --name "bookeo-db-deploy" \
    --template-file "$PROJECT_ROOT/azure/main.bicep" \
    --parameters baseName="$BASE_NAME" location="$LOCATION" sqlAdminLogin="$SQL_ADMIN" sqlAdminPassword="$SQL_PASSWORD" \
    --output none

# Get outputs
SQL_SERVER=$(az deployment group show --resource-group "$RESOURCE_GROUP" --name "bookeo-db-deploy" --query properties.outputs.sqlServerFqdn.value -o tsv)
SQL_DB=$(az deployment group show --resource-group "$RESOURCE_GROUP" --name "bookeo-db-deploy" --query properties.outputs.sqlDatabaseName.value -o tsv)

echo ""
echo "=== Adding firewall rule for your IP (for local script access) ==="
MY_IP=$(curl -s -4 ifconfig.me 2>/dev/null || curl -s -4 icanhazip.com 2>/dev/null)
echo "Your IP: $MY_IP"
az sql server firewall-rule create \
    --resource-group "$RESOURCE_GROUP" \
    --server "${BASE_NAME}-sqlserver" \
    --name "ClientIP" \
    --start-ip-address "$MY_IP" \
    --end-ip-address "$MY_IP" \
    --output none 2>/dev/null || true

echo ""
echo "=== Running schema script ==="
# Use sqlcmd if available, else print instructions
if command -v sqlcmd &> /dev/null; then
    sqlcmd -S "${BASE_NAME}-sqlserver.database.windows.net" -d "$SQL_DB" -U "$SQL_ADMIN" -P "$SQL_PASSWORD" -i "$PROJECT_ROOT/sql/schema.sql"
else
    echo "sqlcmd not found. Run the schema manually:"
    echo "  sqlcmd -S $SQL_SERVER -d $SQL_DB -U $SQL_ADMIN -P <password> -i $PROJECT_ROOT/sql/schema.sql"
fi

echo ""
echo "=== Done! Add to .env ==="
echo "AZURE_SQL_SERVER=$SQL_SERVER"
echo "AZURE_SQL_DATABASE=$SQL_DB"
echo "AZURE_SQL_USER=$SQL_ADMIN"
echo "AZURE_SQL_PASSWORD=<your-password>"
echo ""
echo "Then run: python scripts/load_bookeo_bookings.py --months 24"
