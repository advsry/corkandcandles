// Azure Bicep - Bookeo Bookings Database
// Deploys: Resource Group, SQL Server, SQL Database, Firewall rule for Azure services

@description('Base name for resources')
param baseName string = 'corkandcandles'

@description('Azure region')
param location string = 'vnet-eastus-bastion'

@description('SQL admin login')
param sqlAdminLogin string

@secure()
@description('SQL admin password')
param sqlAdminPassword string

@description('Number of months to fetch (from Jan 2026)')
param monthsToFetch int = 24

var sqlServerName = '${baseName}-sqlserver'
var sqlDatabaseName = '${baseName}-bookings'

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: sqlServerName
  location: location
  properties: {
    administratorLogin: sqlAdminLogin
    administratorLoginPassword: sqlAdminPassword
    version: '12.0'
    minimalTlsVersion: '1.2'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
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

resource firewallRule 'Microsoft.Sql/servers/firewallRules@2023-05-01-preview' = {
  parent: sqlServer
  name: 'AllowAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output sqlServerFqdn string = sqlServer.properties.fullyQualifiedDomainName
output sqlDatabaseName string = sqlDatabase.name
output connectionString string = 'Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Initial Catalog=${sqlDatabaseName};Persist Security Info=False;User ID=${sqlAdminLogin};Password=${sqlAdminPassword};Encrypt=True;TrustServerCertificate=False;Connection Timeout=30;'
