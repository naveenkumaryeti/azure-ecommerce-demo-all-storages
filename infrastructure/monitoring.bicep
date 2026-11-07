// Azure Monitor: Log Analytics workspace + Blob diagnostic logs (read/write/delete) + metrics
param location string
param storageName string

resource law 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'ecommerce-logs'
  location: location
  properties: { sku: { name: 'PerGB2018' }, retentionInDays: 30 }
}
resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' existing = { name: storageName }
resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' existing = { parent: sa, name: 'default' }

resource diag 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: 'blob-to-law'
  scope: blobSvc
  properties: {
    workspaceId: law.id
    logs: [
      { category: 'StorageRead', enabled: true }
      { category: 'StorageWrite', enabled: true }
      { category: 'StorageDelete', enabled: true }
    ]
    metrics: [ { category: 'Transaction', enabled: true } ]
  }
}
