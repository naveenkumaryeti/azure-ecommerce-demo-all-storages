# Deployment

**Automated:** `cd scripts && ./deploy.sh [subscription]`. It does steps 1-17 below via `infrastructure/main.bicep`. Manual Azure CLI equivalents (explained) follow; set variables first:
```bash
RG=rg-ecommerce-demo; LOC=centralindia; SA=ecom$RANDOM$RANDOM; VNET=ecommerce-vnet
```
| # | Step | Command / explanation |
|---|---|---|
| 1 | Login | `az login` – interactive Entra sign-in |
| 2 | Subscription | `az account set --subscription "<name-or-id>"` |
| 3 | Resource group | `az group create -n $RG -l $LOC` – container for all resources |
| 4 | VNet+subnets | `az network vnet create -g $RG -n $VNET --address-prefixes 10.20.0.0/16 --subnet-name frontend-subnet --subnet-prefixes 10.20.1.0/24` then `az network vnet subnet create -g $RG --vnet-name $VNET -n backend-subnet --address-prefixes 10.20.2.0/24` and `-n private-endpoint-subnet --address-prefixes 10.20.3.0/24` |
| 5 | ASGs | `az network asg create -g $RG -n asg-frontend` ; `... -n asg-backend` |
| 6 | NSGs | `az network nsg create -g $RG -n nsg-frontend` ; `nsg-backend`; rules: `az network nsg rule create -g $RG --nsg-name nsg-backend -n Allow-API-From-Frontend --priority 100 --access Allow --protocol Tcp --direction Inbound --source-asgs asg-frontend --destination-asgs asg-backend --destination-port-ranges 5000` plus `Allow-HTTP-Internet` (80, source Internet) on the frontend and `Deny-All-Inbound` priority 4000; attach: `az network vnet subnet update -g $RG --vnet-name $VNET -n backend-subnet --network-security-group nsg-backend` |
| 7 | Storage | `az storage account create -g $RG -n $SA -l $LOC --sku Standard_LRS --allow-blob-public-access false --allow-shared-key-access false --public-network-access Disabled --min-tls-version TLS1_2` |
| 8 | Containers | Bicep creates them (data-plane CLI needs a reachable endpoint + role): `az storage container create --account-name $SA -n products --auth-mode login` for products, product-images, orders, audit-logs, application-backups |
| 9 | Private endpoint | `az network private-endpoint create -g $RG -n $SA-pe --vnet-name $VNET --subnet private-endpoint-subnet --private-connection-resource-id $(az storage account show -g $RG -n $SA --query id -o tsv) --group-id blob --connection-name blob` |
| 10 | Private DNS | `az network private-dns zone create -g $RG -n privatelink.blob.core.windows.net` ; `az network private-dns link vnet create -g $RG -z privatelink.blob.core.windows.net -n vnet-link -v $VNET -e false` ; `az network private-endpoint dns-zone-group create -g $RG --endpoint-name $SA-pe -n default --private-dns-zone privatelink.blob.core.windows.net --zone-name blob` |
| 11 | Managed Identity | `az vmss identity assign -g $RG -n backend-vmss` (Bicep: `identity: SystemAssigned`) ; `PID=$(az vmss show -g $RG -n backend-vmss --query identity.principalId -o tsv)` |
| 12 | RBAC | `az role assignment create --assignee-object-id $PID --assignee-principal-type ServicePrincipal --role "Storage Blob Data Contributor" --scope $(az storage account show -g $RG -n $SA --query id -o tsv)` ; verify `az role assignment list --assignee $PID -o table` |
| 13 | VMSS | `az vmss create ... --custom-data cloud-init.yaml --vm-sku Standard_B2s --instance-count 2 --lb <lb> --asgs asg-backend` (Bicep `vmss.bicep`); autoscale: `az monitor autoscale create -g $RG --resource backend-vmss --resource-type Microsoft.Compute/virtualMachineScaleSets --min-count 1 --count 2 --max-count 4 -n backend-as` + `az monitor autoscale rule create ... --condition "Percentage CPU > 70 avg 5m" --scale out 1` and `"< 30 avg 5m" --scale in 1` |
| 14-15 | Frontend / backend code | Delivered by cloud-init (`deploy.sh` base64-embeds `frontend/` and `backend/`); nginx proxies `/api` to `10.20.2.10:5000`. |
| 16 | App test | `./test-storage.sh accept` |
| 17 | Blob verification | Explorer page, or `curl http://<ip>/api/storage/containers/products/blobs` |

## Expected output
`deploy.sh` ends with `Open: http://<public-ip>`; RBAC table shows `Storage Blob Data Contributor`; `accept` ends `PASS=17 FAIL=0`.

## Verify in Azure Portal
Storage account → Containers (needs *Storage Blob Data Reader* for you + temporary IP rule, see README), Networking (public access Disabled, private endpoint), IAM (role assignment for `backend-vmss`), VMSS → Instances/Scaling, Monitor → Logs (`StorageBlobLogs`).

## Phase 2 migration, deployment and rollback
**Migrating a running Phase-1 deployment:** Phase-2 changes the product JSON schema (`name`->`product_name`, `quantity`->`available_quantity`, `image_url`->`image_blob_name`, + `seller_id`, `publication_status`) and adds queues/tables/PEs/roles/VMSS cloud-init. Recommended: `./cleanup.sh` then `./deploy.sh` (clean, ~15 min). Re-running `deploy.sh` over a live VMSS may be rejected because cloud-init custom data changed. Old products are not shown by the new app; delete old `products/*.json` (Phase-1 demo data) or re-create them in the Seller Portal.
**Code-only updates later:** `./update-app.sh [backend|frontend|all]` (run-command, no VMSS rebuild).
**Deploy:** `./deploy.sh "<subscription>"` prints seller/admin/customer credentials. Then `./test-storage.sh accept`.
**Rollback:** (1) code: check out the previous commit and `./update-app.sh`; (2) infra: re-deploy previous Bicep or `./cleanup.sh`; (3) data: Blob soft-delete (7 days) can restore deleted blobs; queues/tables can be recreated by redeploying. Nothing outside the resource group is touched.
**Background consumer:** `./configure-worker.sh start|stop` (off by default for the classroom demo).
