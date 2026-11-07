// VNet, 3 subnets, 2 ASGs, 2 NSGs, NAT gateway (outbound for package install)
param location string
param vnetName string = 'ecommerce-vnet'

resource asgFe 'Microsoft.Network/applicationSecurityGroups@2023-09-01' = { name: 'asg-frontend', location: location }
resource asgBe 'Microsoft.Network/applicationSecurityGroups@2023-09-01' = { name: 'asg-backend', location: location }

resource natIp 'Microsoft.Network/publicIPAddresses@2023-09-01' = {
  name: 'ecommerce-nat-ip'
  location: location
  sku: { name: 'Standard' }
  properties: { publicIPAllocationMethod: 'Static' }
}
resource nat 'Microsoft.Network/natGateways@2023-09-01' = {
  name: 'ecommerce-nat'
  location: location
  sku: { name: 'Standard' }
  properties: { publicIpAddresses: [ { id: natIp.id } ], idleTimeoutInMinutes: 4 }
}

// ---- Frontend NSG: internet -> 80/443 on asg-frontend; everything else denied ----
resource nsgFe 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: 'nsg-frontend'
  location: location
  properties: {
    securityRules: [
      { name: 'Allow-HTTP-Internet', properties: { priority: 100, direction: 'Inbound', access: 'Allow', protocol: 'Tcp', sourceAddressPrefix: 'Internet', sourcePortRange: '*', destinationApplicationSecurityGroups: [ { id: asgFe.id } ], destinationPortRange: '80' } }
      { name: 'Allow-HTTPS-Internet', properties: { priority: 110, direction: 'Inbound', access: 'Allow', protocol: 'Tcp', sourceAddressPrefix: 'Internet', sourcePortRange: '*', destinationApplicationSecurityGroups: [ { id: asgFe.id } ], destinationPortRange: '443' } }
      { name: 'Allow-LB-Probe', properties: { priority: 120, direction: 'Inbound', access: 'Allow', protocol: 'Tcp', sourceAddressPrefix: 'AzureLoadBalancer', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '80' } }
      { name: 'Deny-All-Inbound', properties: { priority: 4000, direction: 'Inbound', access: 'Deny', protocol: '*', sourceAddressPrefix: '*', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '*' } }
      { name: 'Allow-API-To-Backend', properties: { priority: 100, direction: 'Outbound', access: 'Allow', protocol: 'Tcp', sourceApplicationSecurityGroups: [ { id: asgFe.id } ], sourcePortRange: '*', destinationApplicationSecurityGroups: [ { id: asgBe.id } ], destinationPortRange: '5000' } }
    ]
  }
}

// ---- Backend NSG: only asg-frontend -> 5000; SSH only from Bastion subnet; no internet inbound ----
resource nsgBe 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: 'nsg-backend'
  location: location
  properties: {
    securityRules: [
      { name: 'Allow-API-From-Frontend', properties: { priority: 100, direction: 'Inbound', access: 'Allow', protocol: 'Tcp', sourceApplicationSecurityGroups: [ { id: asgFe.id } ], sourcePortRange: '*', destinationApplicationSecurityGroups: [ { id: asgBe.id } ], destinationPortRange: '5000' } }
      { name: 'Allow-LB-Probe', properties: { priority: 110, direction: 'Inbound', access: 'Allow', protocol: 'Tcp', sourceAddressPrefix: 'AzureLoadBalancer', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '5000' } }
      { name: 'Allow-SSH-From-Bastion', properties: { priority: 130, direction: 'Inbound', access: 'Allow', protocol: 'Tcp', sourceAddressPrefix: '10.20.250.0/26', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '22' } }
      { name: 'Deny-Internet-Inbound', properties: { priority: 200, direction: 'Inbound', access: 'Deny', protocol: '*', sourceAddressPrefix: 'Internet', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '*' } }
      { name: 'Deny-All-Inbound', properties: { priority: 4000, direction: 'Inbound', access: 'Deny', protocol: '*', sourceAddressPrefix: '*', sourcePortRange: '*', destinationAddressPrefix: '*', destinationPortRange: '*' } }
      { name: 'Allow-Storage-PrivateEndpoint', properties: { priority: 100, direction: 'Outbound', access: 'Allow', protocol: 'Tcp', sourceApplicationSecurityGroups: [ { id: asgBe.id } ], sourcePortRange: '*', destinationAddressPrefix: '10.20.3.0/24', destinationPortRange: '443' } }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: { addressPrefixes: [ '10.20.0.0/16' ] }
    subnets: [
      { name: 'frontend-subnet', properties: { addressPrefix: '10.20.1.0/24', networkSecurityGroup: { id: nsgFe.id }, natGateway: { id: nat.id } } }
      { name: 'backend-subnet', properties: { addressPrefix: '10.20.2.0/24', networkSecurityGroup: { id: nsgBe.id }, natGateway: { id: nat.id } } }
      { name: 'private-endpoint-subnet', properties: { addressPrefix: '10.20.3.0/24' } }
    ]
  }
}

output vnetId string = vnet.id
output frontendSubnetId string = vnet.properties.subnets[0].id
output backendSubnetId string = vnet.properties.subnets[1].id
output peSubnetId string = vnet.properties.subnets[2].id
output asgFrontendId string = asgFe.id
output asgBackendId string = asgBe.id
