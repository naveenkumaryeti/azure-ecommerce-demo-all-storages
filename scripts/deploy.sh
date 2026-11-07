#!/usr/bin/env bash
# Full deployment: RG -> network/ASG/NSG -> storage+PE+DNS -> VMSS (+identity) -> RBAC -> monitoring.
# Usage: ./deploy.sh [subscription-id-or-name]
set -euo pipefail
cd "$(dirname "$0")"
command -v az >/dev/null || { echo "Azure CLI not found. Install it or use Cloud Shell/WSL."; exit 1; }
echo "==> 1/6 Login & subscription"
az account show >/dev/null 2>&1 || az login -o none
[ -n "${1:-}" ] && az account set --subscription "$1"
source ./env.sh
echo "    subscription: $(az account show --query name -o tsv) | RG=$RG | location=$LOCATION | storage=$STORAGE_NAME"

echo "==> 2/6 Resource group"
az group create -n "$RG" -l "$LOCATION" -o none

echo "==> 3/6 Package application into cloud-init (no secrets inside)"
T=$(mktemp -d); TW=$(W "$T"); trap 'rm -rf "$T"' EXIT
tar czf "$T/backend.tgz" -C "$ROOT/backend" --exclude=__pycache__ .
tar czf "$T/frontend.tgz" -C "$ROOT/frontend" .
# Secrets for the app (kept locally in scripts/.state, never committed). Reused on re-runs so logins stay stable.
mkdir -p "$ROOT/scripts/.state"; ST="$ROOT/scripts/.state/credentials.env"
if [ ! -f "$ST" ]; then
  G() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }
  printf 'SESSION_SECRET=%s\nQK_SELLER_EMAIL=seller@quickkart.demo\nQK_SELLER_PASSWORD=%s\nQK_ADMIN_EMAIL=admin@quickkart.demo\nQK_ADMIN_PASSWORD=%s\nQK_CUSTOMER_EMAIL=customer@quickkart.demo\nQK_CUSTOMER_PASSWORD=%s\n' "$(G 32)" "$(G 12)" "$(G 12)" "$(G 12)" > "$ST"; chmod 600 "$ST"
fi
set -a; source "$ST"; set +a
B64() { base64 < "$1" | tr -d '\n'; }
cat > "$T/backend.yaml" <<YAML
#cloud-config
package_update: true
packages: [python3-pip, python3-venv, stress-ng]
write_files:
- path: /opt/ecommerce/backend.tgz
  encoding: b64
  content: $(B64 "$T/backend.tgz")
- path: /etc/ecommerce.env
  content: |
    STORAGE_ACCOUNT_NAME=$STORAGE_NAME
    SESSION_SECRET=$SESSION_SECRET
    SEED_SELLER_PASSWORD=$QK_SELLER_PASSWORD
    SEED_ADMIN_PASSWORD=$QK_ADMIN_PASSWORD
    SEED_CUSTOMER_PASSWORD=$QK_CUSTOMER_PASSWORD
- path: /etc/systemd/system/ecommerce.service
  content: |
    [Unit]
    Description=Ecommerce Flask API
    After=network-online.target
    [Service]
    DynamicUser=yes
    WorkingDirectory=/opt/ecommerce/app
    EnvironmentFile=/etc/ecommerce.env
    ExecStart=/opt/ecommerce/venv/bin/gunicorn -w 2 -b 0.0.0.0:5000 app:app
    Restart=always
    [Install]
    WantedBy=multi-user.target
- path: /etc/systemd/system/quickkart-worker.service
  content: |
    [Unit]
    Description=QuickKart queue consumer (enable manually: systemctl enable --now quickkart-worker)
    After=network-online.target
    [Service]
    DynamicUser=yes
    WorkingDirectory=/opt/ecommerce/app
    EnvironmentFile=/etc/ecommerce.env
    ExecStart=/opt/ecommerce/venv/bin/python worker.py
    Restart=always
runcmd:
- mkdir -p /opt/ecommerce/app && tar xzf /opt/ecommerce/backend.tgz -C /opt/ecommerce/app
- python3 -m venv /opt/ecommerce/venv
- /opt/ecommerce/venv/bin/pip install -q -r /opt/ecommerce/app/requirements.txt
- systemctl daemon-reload && systemctl enable --now ecommerce
YAML
cat > "$T/frontend.yaml" <<YAML
#cloud-config
package_update: true
packages: [nginx]
write_files:
- path: /opt/frontend.tgz
  encoding: b64
  content: $(B64 "$T/frontend.tgz")
- path: /etc/nginx/conf.d/ecommerce.conf
  content: |
    server {
      listen 80 default_server;
      root /var/www/html;
      index index.html;
      client_max_body_size 6m;
      location /api/ { proxy_pass http://$BACKEND_ILB_IP:5000; proxy_read_timeout 60s; }
    }
runcmd:
- rm -f /etc/nginx/sites-enabled/default /var/www/html/index.nginx-debian.html
- tar xzf /opt/frontend.tgz -C /var/www/html
- systemctl restart nginx
YAML
[ -f ~/.ssh/id_rsa.pub ] || ssh-keygen -q -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa
python3 - "$TW" "$STORAGE_NAME" "$VM_SIZE" "$BACKEND_ILB_IP" <<'PY'
import base64, json, os, sys
t, sa, size, ip = sys.argv[1:5]
b = lambda f: base64.b64encode(open(f"{t}/{f}", "rb").read()).decode()
v = lambda x: {"value": x}
json.dump({"$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
           "contentVersion": "1.0.0.0", "parameters": {
    "storageName": v(sa), "vmSize": v(size), "backendIlbIp": v(ip),
    "sshPublicKey": v(open(os.path.expanduser("~/.ssh/id_rsa.pub")).read().strip()),
    "frontendCustomData": v(b("frontend.yaml")), "backendCustomData": v(b("backend.yaml"))}},
    open(f"{t}/params.json", "w"))
PY

echo "==> 4/6 Deploy Bicep (network, storage, private endpoint, VMSS, RBAC, monitoring) ~10 min"
az deployment group create -g "$RG" -f "$(W "$ROOT/infrastructure/main.bicep")" -p "@$TW/params.json" -o none

echo "==> 5/6 Verify RBAC"
"$ROOT/scripts/configure-rbac.sh" show

echo "==> 6/6 Wait for the site (cloud-init installs packages, 3-6 min)"
IP=$(fe_ip)
for i in $(seq 1 40); do curl -fsS "http://$IP/api/health" >/dev/null 2>&1 && break; sleep 15; done
echo "Open:  http://$IP"
echo "Credentials (also in scripts/.state/credentials.env):"; grep -E '^QK_' "$ST" | sed 's/^/   /'
echo "Test:  ./test-storage.sh accept"
