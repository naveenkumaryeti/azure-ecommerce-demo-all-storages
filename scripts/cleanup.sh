#!/usr/bin/env bash
# Delete EVERYTHING (VMSS, LBs, NAT GW, storage, private endpoint, Log Analytics) to stop billing.
set -euo pipefail; source "$(dirname "$0")/env.sh"
read -rp "Delete resource group '$RG' and all resources? (type yes) " a
[ "$a" = yes ] && az group delete -n "$RG" --yes --no-wait && echo "Deletion started. Verify: az group exists -n $RG"
