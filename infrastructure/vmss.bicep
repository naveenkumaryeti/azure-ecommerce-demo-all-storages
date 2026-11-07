// Reusable tier: load balancer + VM Scale Set (+ managed identity if backend) + CPU autoscale
param name string
param location string
param vmSize string
param adminUsername string
@secure()
param sshPublicKey string
@secure()
param customData string      // base64 cloud-init (built by scripts/deploy.sh)
param subnetId string
param asgId string
param isBackend bool
param lbPublic bool
param lbPrivateIp string = ''
param appPort int
param probePath string
param minCount int = 1
param defaultCount int = 2
param maxCount int = 4

var lbName = '${name}-lb'

resource pip 'Microsoft.Network/publicIPAddresses@2023-09-01' = if (lbPublic) {
  name: '${lbName}-pip'
  location: location
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}

resource lb 'Microsoft.Network/loadBalancers@2023-09-01' = {
  name: lbName
  location: location
  sku: { name: 'Standard' }
  properties: {
    frontendIPConfigurations: [
      lbPublic ? {
        name: 'fe'
        properties: { publicIPAddress: { id: pip.id } }
      } : {
        name: 'fe'
        properties: { subnet: { id: subnetId }, privateIPAllocationMethod: 'Static', privateIPAddress: lbPrivateIp }
      }
    ]
    backendAddressPools: [ { name: 'be' } ]
    probes: [ { name: 'probe', properties: { protocol: 'Http', port: appPort, requestPath: probePath, intervalInSeconds: 15, numberOfProbes: 2 } } ]
    loadBalancingRules: [ {
      name: 'rule'
      properties: {
        frontendIPConfiguration: { id: resourceId('Microsoft.Network/loadBalancers/frontendIPConfigurations', lbName, 'fe') }
        backendAddressPool: { id: resourceId('Microsoft.Network/loadBalancers/backendAddressPools', lbName, 'be') }
        probe: { id: resourceId('Microsoft.Network/loadBalancers/probes', lbName, 'probe') }
        protocol: 'Tcp'
        frontendPort: appPort
        backendPort: appPort
        enableTcpReset: true
        idleTimeoutInMinutes: 4
      }
    } ]
  }
}

resource vmss 'Microsoft.Compute/virtualMachineScaleSets@2023-09-01' = {
  name: name
  location: location
  sku: { name: vmSize, tier: 'Standard', capacity: defaultCount }
  identity: isBackend ? { type: 'SystemAssigned' } : null
  properties: {
    overprovision: false
    upgradePolicy: { mode: 'Manual' }
    virtualMachineProfile: {
      osProfile: {
        computerNamePrefix: take(replace(name, '-vmss', ''), 9)
        adminUsername: adminUsername
        customData: customData
        linuxConfiguration: {
          disablePasswordAuthentication: true
          ssh: { publicKeys: [ { path: '/home/${adminUsername}/.ssh/authorized_keys', keyData: sshPublicKey } ] }
        }
      }
      storageProfile: {
        imageReference: { publisher: 'Canonical', offer: '0001-com-ubuntu-server-jammy', sku: '22_04-lts-gen2', version: 'latest' }
        osDisk: { createOption: 'FromImage', managedDisk: { storageAccountType: 'Standard_LRS' } }
      }
      networkProfile: {
        networkInterfaceConfigurations: [ {
          name: 'nic'
          properties: {
            primary: true
            ipConfigurations: [ {
              name: 'ipconfig'
              properties: {
                subnet: { id: subnetId }
                applicationSecurityGroups: [ { id: asgId } ]
                loadBalancerBackendAddressPools: [ { id: resourceId('Microsoft.Network/loadBalancers/backendAddressPools', lbName, 'be') } ]
              }
            } ]
          }
        } ]
      }
    }
  }
  dependsOn: [ lb ]
}

resource autoscale 'Microsoft.Insights/autoscalesettings@2022-10-01' = {
  name: '${name}-autoscale'
  location: location
  properties: {
    enabled: true
    targetResourceUri: vmss.id
    profiles: [ {
      name: 'cpu-based'
      capacity: { minimum: string(minCount), maximum: string(maxCount), default: string(defaultCount) }
      rules: [
        {
          metricTrigger: { metricName: 'Percentage CPU', metricResourceUri: vmss.id, timeGrain: 'PT1M', statistic: 'Average', timeWindow: 'PT5M', timeAggregation: 'Average', operator: 'GreaterThan', threshold: 70 }
          scaleAction: { direction: 'Increase', type: 'ChangeCount', value: '1', cooldown: 'PT5M' }
        }
        {
          metricTrigger: { metricName: 'Percentage CPU', metricResourceUri: vmss.id, timeGrain: 'PT1M', statistic: 'Average', timeWindow: 'PT5M', timeAggregation: 'Average', operator: 'LessThan', threshold: 30 }
          scaleAction: { direction: 'Decrease', type: 'ChangeCount', value: '1', cooldown: 'PT5M' }
        }
      ]
    } ]
  }
}

output principalId string = isBackend ? vmss.identity.principalId : ''
