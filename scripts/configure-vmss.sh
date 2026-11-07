#!/usr/bin/env bash
# VMSS helper.  ./configure-vmss.sh status|load|stop-load|mi-disable|mi-enable
set -euo pipefail; source "$(dirname "$0")/env.sh"
each() { for i in $(az vmss list-instances -g "$RG" -n "$1" --query "[].instanceId" -o tsv); do az vmss run-command invoke -g "$RG" -n "$1" --instance-id "$i" --command-id RunShellScript --scripts "$2" -o none; done; }
case "${1:-status}" in
  status)  for v in $FRONTEND_VMSS $BACKEND_VMSS; do echo "== $v"; az vmss list-instances -g "$RG" -n $v --query "[].{id:instanceId,name:osProfile.computerName,state:provisioningState}" -o table; done
           az monitor autoscale list -g "$RG" --query "[].{name:name,min:profiles[0].capacity.minimum,default:profiles[0].capacity.default,max:profiles[0].capacity.maximum}" -o table ;;
  load)    echo "Burning CPU on backend instances for 15 min (stress-ng)..."; each $BACKEND_VMSS "nohup stress-ng --cpu 0 --timeout 900s >/dev/null 2>&1 &"
           echo "Watch: watch -n 20 \"az vmss list-instances -g $RG -n $BACKEND_VMSS -o table\"  (scale-out after ~5-8 min)" ;;
  stop-load) each $BACKEND_VMSS "pkill stress-ng || true"; echo "Load stopped; scale-in follows after CPU < 30% for ~5+ min." ;;
  mi-disable) az vmss identity remove -g "$RG" -n $BACKEND_VMSS --identities '[system]' -o none
           az vmss update-instances -g "$RG" -n $BACKEND_VMSS --instance-ids '*'
           echo "Identity removed. API now returns AUTHENTICATION_FAILED (503)." ;;
  mi-enable) az vmss identity assign -g "$RG" -n $BACKEND_VMSS -o none
           az vmss update-instances -g "$RG" -n $BACKEND_VMSS --instance-ids '*'
           echo "A NEW principal was created -> re-grant RBAC: ./configure-rbac.sh add" ;;
  *) echo "usage: $0 status|load|stop-load|mi-disable|mi-enable"; exit 1 ;;
esac
