# 60-Minute Live Demo (`source scripts/env.sh` first; `IP=$(fe_ip)`)

| Min | Topic |
|---|---|
| 5 | Three-tier architecture |
| 10 | Storage Account & Blob |
| 10 | Managed Identity & RBAC |
| 10 | Add product → JSON in Blob |
| 10 | ASG & NSG |
| 5 | Private Endpoint |
| 5 | VMSS autoscaling |
| 5 | Troubleshooting & Q&A |

## 1. Three-tier (5 min)
**Explain:** presentation/app/data separation; why independent scaling & security boundaries. **Portal:** Resource group → resource list. **CLI:** `az resource list -g $RG -o table`. **Expected:** 2 VMSS, 2 LBs, VNet, NSGs, ASGs, storage, PE. **Activity:** students draw request path from browser to blob. **Use case:** retail sites separating web/API/data.

## 2. Storage & Blob (10)
**Explain:** account → containers → blobs, JSON blob per entity, ETag, `allowSharedKeyAccess=false`, public access Disabled. **Portal:** Storage account → Containers (5), Configuration, Networking. **CLI:** `az storage account show -g $RG -n $STORAGE_NAME --query "{keys:allowSharedKeyAccess,public:publicNetworkAccess,tls:minimumTlsVersion}" -o table` **Expected:** `False / Disabled / TLS1_2`. **Activity:** open Explorer page → list containers/blobs. **Use case:** data lake, media store, config/state store.

## 3. Managed Identity & RBAC (10)
**Explain:** see ARCHITECTURE.md (identity, token, RBAC). **Portal:** backend-vmss → Identity; Storage → IAM → Role assignments. **CLI:** `scripts/configure-rbac.sh show` **Expected:** principalId + `Storage Blob Data Contributor`. **Demo failure:** `scripts/configure-rbac.sh remove`, reload dashboard → 403 `AUTHORIZATION_FAILED` after ~2-5 min; `add` restores. **Optional:** `mi-disable` → 503. **Activity:** students state which role they'd give a read-only reporting service (*Storage Blob Data Reader*). **Use case:** apps calling Key Vault/SQL/Storage without secrets.

## 4. Add product → blob (10)
**Explain:** flow UI → nginx → Flask → token → Blob. **Do:** `http://$IP/products.html` → Add Product (name Laptop, price 55000, qty 10, image). **Verify:** Explorer → `products` → `PROD-….json` → View; `product-images` shows the image; `audit-logs/…product_created.json`. **CLI:** `curl -s http://$IP/api/storage/containers/products/blobs`. **Expected:** JSON listing the new blob. Edit price → blob `last_modified` changes; delete → blob disappears. **Activity:** open two tabs, edit same product in both → second save gives 409 (ETag). **Use case:** serverless-style persistence without a DB.

## 5. ASG & NSG (10)
**Explain:** NSG rules by priority, ASG as named NIC group. **Portal:** nsg-backend → Inbound rules; asg-backend → Associated NICs. **CLI:** `az network nsg rule list -g $RG --nsg-name nsg-backend -o table`. **Demo:** `scripts/test-storage.sh nsg-block` → `curl -i http://$IP/api/products` hangs/502 while `http://$IP/` loads → `nsg-unblock`. **Expected:** products list returns after unblock. **Activity:** predict result if rule priority were 110. **Use case:** micro-segmentation, zero-trust east-west control.

## 6. Private Endpoint (5)
**Explain:** PE NIC + private DNS. **Portal:** Storage → Networking → Private endpoints; Private DNS zone → A record. **CLI:** `scripts/test-storage.sh public-access` **Expected:** public curl 403/fails, deep health `status ok`. **Demo:** `dns-break` → API fails; `dns-fix`. **Use case:** PCI/regulated data never on public internet.

## 7. Autoscaling (5)
**Explain:** VM vs VMSS, rules, cooldown. **Portal:** backend-vmss → Scaling. **CLI:** `scripts/configure-vmss.sh status` then `load`; `watch -n 30 az vmss list-instances -g $RG -n backend-vmss -o table`. **Expected:** 2→3→4 instances within ~10 min (start this at minute 0 of the class!). Reload dashboard: "Served by" shows different instances. `stop-load` afterwards. **Use case:** seasonal sales spikes.

## 8. Troubleshooting & Q&A (5)
Walk TROUBLESHOOTING.md table; run `scripts/test-storage.sh accept` live → `PASS=17 FAIL=0`. Finish with `scripts/cleanup.sh`.
