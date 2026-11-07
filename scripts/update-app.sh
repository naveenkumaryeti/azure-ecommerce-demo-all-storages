#!/usr/bin/env bash
# Push new application code (and env file) to RUNNING instances without recreating the VMSS.  ./update-app.sh [backend|frontend|all]
# Infra changes (queues, tables, private endpoints, RBAC) still need deploy.sh. New VMSS instances created later use the cloud-init from the last deploy.sh.
set -euo pipefail; source "$(dirname "$0")/env.sh"
ST="$ROOT/scripts/.state/credentials.env"; set -a; source "$ST"; set +a
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT; WHAT="${1:-all}"
push() { # $1 vmss  $2 tgz  $3 script
  B=$(base64 < "$2" | tr -d '\n')
  for i in $(az vmss list-instances -g "$RG" -n "$1" --query "[].instanceId" -o tsv); do
    echo "updating $1 instance $i"; az vmss run-command invoke -g "$RG" -n "$1" --instance-id "$i" --command-id RunShellScript --scripts "echo $B | base64 -d > /tmp/app.tgz" "$3" --query "value[0].message" -o tsv | tail -2
  done; }
if [ "$WHAT" != frontend ]; then
  tar czf "$T/b.tgz" -C "$ROOT/backend" --exclude=__pycache__ .
  push $BACKEND_VMSS "$T/b.tgz" "set -e; mkdir -p /opt/ecommerce/app; tar xzf /tmp/app.tgz -C /opt/ecommerce/app; printf 'STORAGE_ACCOUNT_NAME=$STORAGE_NAME\nSESSION_SECRET=$SESSION_SECRET\nSEED_SELLER_PASSWORD=$QK_SELLER_PASSWORD\nSEED_ADMIN_PASSWORD=$QK_ADMIN_PASSWORD\nSEED_CUSTOMER_PASSWORD=$QK_CUSTOMER_PASSWORD\n' > /etc/ecommerce.env; /opt/ecommerce/venv/bin/pip install -q -r /opt/ecommerce/app/requirements.txt; systemctl restart ecommerce; systemctl is-active quickkart-worker >/dev/null 2>&1 && systemctl restart quickkart-worker || true; echo backend updated"
fi
if [ "$WHAT" != backend ]; then
  tar czf "$T/f.tgz" -C "$ROOT/frontend" .
  push $FRONTEND_VMSS "$T/f.tgz" "set -e; rm -rf /var/www/html/*; tar xzf /tmp/app.tgz -C /var/www/html; echo frontend updated"
fi
