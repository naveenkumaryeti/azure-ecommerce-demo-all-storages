// Entry point: az deployment group create -g <rg> -f main.bicep -p params.json
targetScope = 'resourceGroup'
param location string = resourceGroup().location
param storageName string
param adminUsername string = 'azureuser'
param vmSize string = 'Standard_B2s'
param backendIlbIp string = '10.20.2.10'
@secure()
param sshPublicKey string
@secure()
param frontendCustomData string
@secure()
param backendCustomData string

module net 'networking.bicep' = { name: 'net', params: { location: location } }

module storage 'storage.bicep' = {
  name: 'storage'
  params: { location: location, storageName: storageName, peSubnetId: net.outputs.peSubnetId, vnetId: net.outputs.vnetId }
}

module backend 'vmss.bicep' = {
  name: 'backend'
  params: {
    name: 'backend-vmss', location: location, vmSize: vmSize, adminUsername: adminUsername, sshPublicKey: sshPublicKey
    customData: backendCustomData, subnetId: net.outputs.backendSubnetId, asgId: net.outputs.asgBackendId
    isBackend: true, lbPublic: false, lbPrivateIp: backendIlbIp, appPort: 5000, probePath: '/api/health'
  }
  dependsOn: [ storage ]
}

module frontend 'vmss.bicep' = {
  name: 'frontend'
  params: {
    name: 'frontend-vmss', location: location, vmSize: vmSize, adminUsername: adminUsername, sshPublicKey: sshPublicKey
    customData: frontendCustomData, subnetId: net.outputs.frontendSubnetId, asgId: net.outputs.asgFrontendId
    isBackend: false, lbPublic: true, appPort: 80, probePath: '/'
  }
}

module identity 'identity.bicep' = {
  name: 'identity'
  params: { principalId: backend.outputs.principalId, storageName: storageName }
  dependsOn: [ storage ]
}

module monitoring 'monitoring.bicep' = {
  name: 'monitoring'
  params: { location: location, storageName: storageName }
  dependsOn: [ storage ]
}
