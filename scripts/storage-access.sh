#!/usr/bin/env bash
# Temporary read-only access for YOU to browse Blob/Queue/Table from Azure Portal, VS Code or Storage Explorer.
#   ./storage-access.sh on      grant yourself *Reader roles + allow your public IP
#   ./storage-access.sh check   list blobs / queue messages / table rows from the CLI (Entra login, no keys)
#   ./storage-access.sh off     REVERT everything (do this when finished)
set -euo pipefail; source "$(dirname "$0")/env.sh"
ME=$(az ad signed-in-user show --query id -o tsv); SCOPE=$(az storage account show -g "$RG" -n "$STORAGE_NAME" --query id -o tsv)
ROLES=("Storage Blob Data Reader" "Storage Queue Data Reader" "Storage Table Data Reader")
A="--account-name $STORAGE_NAME --auth-mode login"
case "${1:-check}" in
  on)  IP=$(curl -s https://api.ipify.org)
       for R in "${ROLES[@]}"; do az role assignment create --assignee-object-id "$ME" --assignee-principal-type User --role "$R" --scope "$SCOPE" -o none; done
       az storage account update -g "$RG" -n "$STORAGE_NAME" --public-network-access Enabled --default-action Deny -o none
       az storage account network-rule add -g "$RG" --account-name "$STORAGE_NAME" --ip-address "$IP" -o none
       echo "Access for $IP granted. Wait 2-5 min (RBAC + firewall propagation), then open the portal / VS Code." ;;
  check) for c in products product-images orders audit-logs; do echo "== blobs: $c"; az storage blob list $A -c $c --query "[].{name:name,size:properties.contentLength,modified:properties.lastModified}" -o table; done
       echo "== queue quickkart-order-queue (peek)"; az storage message peek $A --queue-name quickkart-order-queue -o table || true
       echo "== poison queue (peek)"; az storage message peek $A --queue-name quickkart-order-poison -o table || true
       for t in TableQueue TableService; do echo "== table $t"; az storage entity query $A --table-name $t --query "items[].{Order:OrderID,Queue:QueueStatus,Order_:OrderStatus,Pay:PaymentStatus,Delivery:DeliveryStatus}" -o table || true; done ;;
  off) IP=$(curl -s https://api.ipify.org)
       az storage account network-rule remove -g "$RG" --account-name "$STORAGE_NAME" --ip-address "$IP" -o none || true
       az storage account update -g "$RG" -n "$STORAGE_NAME" --public-network-access Disabled -o none
       for R in "${ROLES[@]}"; do az role assignment delete --assignee "$ME" --role "$R" --scope "$SCOPE" || true; done
       echo "Reverted: public access Disabled, your roles removed." ;;
  *) echo "usage: $0 on|check|off"; exit 1 ;;
esac