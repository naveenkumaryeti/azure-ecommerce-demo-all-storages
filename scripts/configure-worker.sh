#!/usr/bin/env bash
# Background queue consumer on every backend instance.  ./configure-worker.sh start|stop|status
# Default is OFF so the demo can show the message waiting in the queue and run the consumer by hand from the Admin dashboard.
set -euo pipefail; source "$(dirname "$0")/env.sh"
case "${1:-status}" in start) C="systemctl enable --now quickkart-worker";; stop) C="systemctl disable --now quickkart-worker";; status) C="systemctl is-active quickkart-worker || true";; *) echo "usage: $0 start|stop|status"; exit 1;; esac
for i in $(az vmss list-instances -g "$RG" -n "$BACKEND_VMSS" --query "[].instanceId" -o tsv); do
  echo "instance $i:"; az vmss run-command invoke -g "$RG" -n "$BACKEND_VMSS" --instance-id "$i" --command-id RunShellScript --scripts "$C" --query "value[0].message" -o tsv
done
