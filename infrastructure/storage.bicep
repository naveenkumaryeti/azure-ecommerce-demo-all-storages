// Storage account (keys off, public access off) + Blob containers + Queues + Tables + private endpoints (blob/queue/table) + private DNS
param location string
param storageName string
param peSubnetId string
param vnetId string
param containers array = [ 'products', 'product-images', 'orders', 'audit-logs', 'application-backups', 'users', 'carts' ]
param queues array = [ 'quickkart-order-queue', 'quickkart-order-poison' ]
param tables array = [ 'TableQueue', 'TableService' ]
var services = [ 'blob', 'queue', 'table' ]

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false      // account keys disabled: Entra ID + RBAC only (works for Blob, Queue and Table)
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Disabled'  // reachable only through private endpoints
    networkAcls: { defaultAction: 'Deny', bypass: 'None' }
  }
}
resource blobSvc 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: sa
  name: 'default'
  properties: { deleteRetentionPolicy: { enabled: true, days: 7 } }
}
resource cs 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for c in containers: {
  parent: blobSvc
  name: c
  properties: { publicAccess: 'None' }
}]
resource queueSvc 'Microsoft.Storage/storageAccounts/queueServices@2023-01-01' = { parent: sa, name: 'default' }
resource qs 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = [for q in queues: { parent: queueSvc, name: q }]
resource tableSvc 'Microsoft.Storage/storageAccounts/tableServices@2023-01-01' = { parent: sa, name: 'default' }
resource ts 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = [for t in tables: { parent: tableSvc, name: t }]

resource pe 'Microsoft.Network/privateEndpoints@2023-09-01' = [for s in services: {
  name: '${storageName}-${s}-pe'
  location: location
  properties: {
    subnet: { id: peSubnetId }
    privateLinkServiceConnections: [ { name: s, properties: { privateLinkServiceId: sa.id, groupIds: [ s ] } } ]
  }
}]
resource zone 'Microsoft.Network/privateDnsZones@2020-06-01' = [for s in services: {
  name: 'privatelink.${s}.${environment().suffixes.storage}'
  location: 'global'
}]
resource link 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [for (s, i) in services: {
  parent: zone[i]
  name: 'vnet-link'
  location: 'global'
  properties: { virtualNetwork: { id: vnetId }, registrationEnabled: false }
}]
resource zg 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-09-01' = [for (s, i) in services: {
  parent: pe[i]
  name: 'default'
  properties: { privateDnsZoneConfigs: [ { name: s, properties: { privateDnsZoneId: zone[i].id } } ] }
}]

output storageId string = sa.id
output blobEndpoint string = sa.properties.primaryEndpoints.blob
