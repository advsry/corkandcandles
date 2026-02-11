// Azure Bicep - Bookeo Webhook Function App
// Deploys: Storage Account, Linux Consumption Function App
// Run after main.bicep; then deploy code with: func azure functionapp publish <name>

@description('Base name for resources')
param baseName string = 'corkandcandles'

@description('Azure region')
param location string = resourceGroup().location

@description('Azure SQL server FQDN (e.g. corkandcandles.database.windows.net)')
param sqlServerFqdn string

@description('SQL database name')
param sqlDatabaseName string = 'corkandcandles-bookings'

@description('SQL admin login')
param sqlAdminLogin string

@secure()
@description('SQL admin password')
param sqlAdminPassword string

@secure()
@description('Bookeo secret key (for webhook signature verification)')
param bookeoSecretKey string

@description('Full webhook URL after deployment (e.g. https://corkandcandles-webhook.azurewebsites.net/api/bookeo)')
param webhookUrl string

var storageAccountName = '${replace(baseName, '-', '')}webhook'
var functionAppName = '${baseName}-webhook'

resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
}

resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    httpsOnly: true
    serverFarmId: appServicePlan.id
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(functionAppName)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AZURE_SQL_SERVER'
          value: sqlServerFqdn
        }
        {
          name: 'AZURE_SQL_DATABASE'
          value: sqlDatabaseName
        }
        {
          name: 'AZURE_SQL_USER'
          value: sqlAdminLogin
        }
        {
          name: 'AZURE_SQL_PASSWORD'
          value: sqlAdminPassword
        }
        {
          name: 'BOOKEO_SECRET_KEY'
          value: bookeoSecretKey
        }
        {
          name: 'BOOKEO_WEBHOOK_URL'
          value: webhookUrl
        }
      ]
    }
  }
}

output functionAppName string = functionApp.name
output webhookUrl string = 'https://${functionApp.properties.defaultHostName}/api/bookeo'
