// Azure Bicep - Bookeo Bookings Database
// Uses existing SQL Server: corkandcandles.database.windows.net (West US 2)
// Deploys: SQL Database + Firewall rule on existing server

@description('Existing SQL Server name')
param sqlServerName string = 'corkandcandles'

@description('Resource group containing the existing SQL Server (default: deployment target)')
param sqlServerResourceGroup string = resourceGroup().name

@description('Azure region (West US 2 for existing server)')
param location string = 'westus2'

@description('SQL admin login')
param sqlAdminLogin string

@secure()
@description('SQL admin password')
param sqlAdminPassword string

@description('Database name')
param sqlDatabaseName string = 'corkandcandles-bookings'

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' existing = {
  name: sqlServerName
  scope: resourceGroup(sqlServerResourceGroup)
}

resource sqlDatabase 'corkandcandles' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    maxSizeBytes: 2147483648 // 2 GB
  }
}

// Firewall rule skipped - configure on existing server as needed

var serverFqdn = '${sqlServerName}.database.windows.net'
output sqlServerFqdn string = serverFqdn
output sqlDatabaseName string = sqlDatabase.name
output connectionString string = 'Server=tcp:${serverFqdn},1433;Initial Catalog=${sqlDatabaseName};Persist Security Info=False;User ID=${sqlAdminLogin};Password=${sqlAdminPassword};Encrypt=True;TrustServerCertificate=False;Connection Timeout=3000;'
