#!/bin/bash
# Deploy Bookeo Bookings database to existing SQL Server (corkandcandles.database.windows.net, West US 2)
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
RESOURCE_GROUP="${RESOURCE_GROUP:-CandC_Franchisor}"
LOCATION="${LOCATION:-westus2}"
SQL_SERVER_NAME="${SQL_SERVER_NAME:-corkandcandles}"
SQL_SERVER_FQDN="${SQL_SERVER_FQDN:-corkandcandles.database.windows.net}"
SQL_SERVER_RG="${SQL_SERVER_RG:-$RESOURCE_GROUP}"
SQL_DATABASE_NAME="${SQL_DATABASE_NAME:-corkandcandles-bookings}"
SQL_ADMIN="${SQL_ADMIN:-sqladmin}"

echo "=== Deploying Bookeo Bookings to Existing SQL Server ==="
echo "Resource Group: $SQL_SERVER_RG"
echo "SQL Server: $SQL_SERVER_FQDN (West US 2)"
echo "Database: $SQL_DATABASE_NAME"
echo ""

# Check Azure CLI
if ! command -v az &> /dev/null; then
    echo "Azure CLI not found. Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi

# Login if needed
az account show &> /dev/null || az login

# Deploy to the resource group containing the SQL server
echo "Deploying to resource group: $SQL_SERVER_RG"
az group show --name "$SQL_SERVER_RG" --output none 2>/dev/null || { echo "Resource group $SQL_SERVER_RG not found. Ensure the SQL server exists there."; exit 1; }

# Prompt for password
read -sp "SQL admin password: " SQL_PASSWORD
echo ""
if [ ${#SQL_PASSWORD} -lt 8 ]; then
    echo "Password must be at least 8 characters"
    exit 1
fi

# Deploy Bicep (database only - uses existing server)
echo "Deploying database to existing SQL server..."
az deployment group create \
    --resource-group "$SQL_SERVER_RG" \
    --name "bookeo-db-deploy" \
    --template-file "$PROJECT_ROOT/azure/main.bicep" \
    --parameters sqlServerName="$SQL_SERVER_NAME" sqlServerResourceGroup="$SQL_SERVER_RG" location="$LOCATION" sqlDatabaseName="$SQL_DATABASE_NAME" sqlAdminLogin="$SQL_ADMIN" sqlAdminPassword="$SQL_PASSWORD" \
    --output none

echo ""
echo "=== Adding firewall rule for your IP (for local script access) ==="
MY_IP=$(curl -s -4 ifconfig.me 2>/dev/null || curl -s -4 icanhazip.com 2>/dev/null)
echo "Your IP: $MY_IP"
az sql server firewall-rule create \
    --resource-group "$SQL_SERVER_RG" \
    --server "$SQL_SERVER_NAME" \
    --name "ClientIP" \
    --start-ip-address "$MY_IP" \
    --end-ip-address "$MY_IP" \
    --output none 2>/dev/null || true

echo ""
echo "=== Running schema script ==="
if command -v sqlcmd &> /dev/null; then
    sqlcmd -S "$SQL_SERVER_FQDN" -d "$SQL_DATABASE_NAME" -U "$SQL_ADMIN" -P "$SQL_PASSWORD" -i "$PROJECT_ROOT/sql/schema.sql"
else
    echo "sqlcmd not found. Run the schema manually:"
    echo "  sqlcmd -S $SQL_SERVER_FQDN -d $SQL_DATABASE_NAME -U $SQL_ADMIN -P <password> -i $PROJECT_ROOT/sql/schema.sql"
fi

echo ""
echo "=== Done! Add to .env ==="
echo "AZURE_SQL_SERVER=$SQL_SERVER_FQDN"
echo "AZURE_SQL_DATABASE=$SQL_DATABASE_NAME"
echo "AZURE_SQL_USER=$SQL_ADMIN"
echo "AZURE_SQL_PASSWORD=<your-password>"
echo ""
echo "Then run: python scripts/load_bookeo_bookings.py --months 24"
