#!/usr/bin/env bash
# RBAC helper.  ./configure-rbac.sh show|add|remove      Optional: ROLE="Storage Queue Data Contributor" to touch one role only.
set -euo pipefail; source "$(dirname "$0")/env.sh"
ALL=("Storage Blob Data Contributor" "Storage Queue Data Contributor" "Storage Table Data Contributor")
[ -n "${ROLE:-}" ] && ROLES=("$ROLE") || ROLES=("${ALL[@]}")
PID=$(az vmss show -g "$RG" -n "$BACKEND_VMSS" --query identity.principalId -o tsv)
SCOPE=$(az storage account show -g "$RG" -n "$STORAGE_NAME" --query id -o tsv)
echo "principalId=$PID"; echo "scope=$SCOPE"
case "${1:-show}" in
  show)   az role assignment list --assignee "$PID" --scope "$SCOPE" --query "[].{role:roleDefinitionName,scope:scope}" -o table ;;
  add)    for R in "${ROLES[@]}"; do az role assignment create --assignee-object-id "$PID" --assignee-principal-type ServicePrincipal --role "$R" --scope "$SCOPE" -o none && echo "added: $R"; done
          echo "RBAC can take up to ~5 min to propagate." ;;
  remove) for R in "${ROLES[@]}"; do az role assignment delete --assignee "$PID" --role "$R" --scope "$SCOPE" && echo "removed: $R"; done
          echo "Matching API calls now fail with AUTHORIZATION_FAILED (HTTP 403) after propagation (1-5 min)." ;;
  *) echo "usage: $0 show|add|remove"; exit 1 ;;
esac
