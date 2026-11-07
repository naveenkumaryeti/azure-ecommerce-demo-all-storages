// RBAC for the backend VMSS system-assigned identity: least privilege per storage service
param principalId string
param storageName string

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' existing = { name: storageName }

var roles = [
  { name: 'Storage Blob Data Contributor', id: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' }
  { name: 'Storage Queue Data Contributor', id: '974c5e8b-45b9-4653-ba55-5f855dd0fb88' }
  { name: 'Storage Table Data Contributor', id: '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3' }
]
// Scope = the storage account (the narrowest scope that covers all containers, both queues and both tables).
resource ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for r in roles: {
  scope: sa
  name: guid(sa.id, principalId, r.id)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', r.id)
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}]
