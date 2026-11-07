#!/usr/bin/env bash
# Acceptance tests + failure scenarios.
# ./test-storage.sh accept | nsg-block | nsg-unblock | dns-break | dns-fix | public-access
set -u; source "$(dirname "$0")/env.sh"
BASE="http://$(fe_ip)"; PASS=0; FAIL=0; ZONE="privatelink.blob.core.windows.net"
ok()  { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad() { echo "  FAIL  $1"; FAIL=$((FAIL+1)); }
chk() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
jq_() { python3 -c "import sys,json; d=json.load(sys.stdin); print($1)"; }
blobs() { curl -fsS "$BASE/api/storage/containers/$1/blobs" | jq_ "' '.join(b['name'] for b in d)"; }

accept() {
  python3 "$(W "$ROOT/scripts/e2e_test.py")" --url "$BASE" || FAIL=$((FAIL+1))
  echo "== Infrastructure checks"
  chk "shared-key access disabled (no keys usable)" "[ \"\$(az storage account show -g $RG -n $STORAGE_NAME --query allowSharedKeyAccess -o tsv)\" = false ]"
  chk "RBAC: Blob + Queue + Table Data Contributor assigned" "[ \"\$($ROOT/scripts/configure-rbac.sh show | grep -c 'Data Contributor')\" -ge 3 ]"
  chk "NSG uses ASGs for port 5000 rule" "az network nsg rule show -g $RG --nsg-name nsg-backend -n Allow-API-From-Frontend --query 'sourceApplicationSecurityGroups[0].id' -o tsv | grep -q asg-frontend"
  chk "3 private endpoints (blob, queue, table), public access Disabled" "[ \"\$(az storage account show -g $RG -n $STORAGE_NAME --query publicNetworkAccess -o tsv)\" = Disabled ] && [ \"\$(az network private-endpoint list -g $RG --query 'length(@)' -o tsv)\" -ge 3 ]"
  chk "autoscale settings (max 4) exist" "az monitor autoscale list -g $RG --query '[].profiles[0].capacity.maximum' -o tsv | grep -q 4"
  echo "== infra PASS=$PASS FAIL=$FAIL"; [ $FAIL -eq 0 ]
}

case "${1:-accept}" in
  accept) accept ;;
  nsg-block)   az network nsg rule create -g "$RG" --nsg-name nsg-backend -n Deny-Frontend-Test --priority 90 --access Deny --protocol Tcp --direction Inbound \
                 --source-asgs asg-frontend --destination-asgs asg-backend --destination-port-ranges 5000 -o table
               echo "Wait ~30s, then: curl -i $BASE/api/products  -> 504/502 from nginx (backend unreachable)" ;;
  nsg-unblock) az network nsg rule delete -g "$RG" --nsg-name nsg-backend -n Deny-Frontend-Test && echo "Rule removed; traffic restored." ;;
  dns-break)   az network private-dns link vnet delete -g "$RG" -z "$ZONE" -n vnet-link -y
               echo "VNet no longer resolves the private IP -> public IP (blocked). Wait ~1 min: curl $BASE/api/products -> 403/503" ;;
  dns-fix)     az network private-dns link vnet create -g "$RG" -z "$ZONE" -n vnet-link -v "$VNET" -e false -o table && echo "DNS link restored." ;;
  public-access) az storage account show -g "$RG" -n "$STORAGE_NAME" --query "{publicNetworkAccess:publicNetworkAccess,sharedKey:allowSharedKeyAccess}" -o table
               echo "--- from this machine (public internet) -> must fail:"
               curl -sS -o /dev/null -w "HTTP %{http_code}\n" "https://$STORAGE_NAME.blob.core.windows.net/products?restype=container&comp=list" || true
               echo "--- through the backend (private endpoint) -> must work:"; curl -fsS "$BASE/api/health?deep=1" ;;
  *) echo "usage: $0 accept|nsg-block|nsg-unblock|dns-break|dns-fix|public-access"; exit 1 ;;
esac
