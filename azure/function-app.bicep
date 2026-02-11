// Azure Bicep - Bookeo Webhook Function App (Linux)
// Deploys: ACR, Storage Account, Linux Function App with custom Docker image
// Run after main.bicep; build/push image and deploy with: ./scripts/deploy_webhook.sh

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
var acrName = take('${replace(baseName, '-', '')}acr', 24)

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: acrName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2022-03-01' = {
  name: '${functionAppName}-plan'
  location: location
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  kind: 'linux'
  properties: {
    reserved: true
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
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    reserved: true
    httpsOnly: true
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'DOCKER|${acr.properties.loginServer}/webhook:latest'
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
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${acr.properties.loginServer}'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_USERNAME'
          value: acr.listCredentials().username
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_PASSWORD'
          value: acr.listCredentials().passwords[0].value
        }
      ]
    }
  }
}

output functionAppName string = functionApp.name
output acrLoginServer string = acr.properties.loginServer
output webhookUrl string = 'https://${functionApp.properties.defaultHostName}/api/bookeo'
