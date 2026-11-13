# QuickKart Storage Cross-Check Guide (Azure CLI + Azure Portal)

Goal: prove that what the app shows is really stored in Azure **Blob**, **Queue** and **Table** Storage.

## 0. Why you cannot browse storage by default
The storage account has **public network access disabled**, **shared keys disabled**, and is reachable only through private endpoints. So the portal and CLI are blocked until you (a) give your own login a read-only role and (b) allow your public IP. Both are temporary and fully reversible.

Run everything from the `scripts/` folder in Git Bash (or WSL / Cloud Shell).

```bash
cd scripts
source env.sh        # loads $RG and $STORAGE_NAME
az login             # skip if already logged in
```

## 1. Open temporary read-only access

### Option A: one command
```bash
./storage-access.sh on
```
Then wait **2-5 minutes** for role and firewall propagation.

# Azure Storage Access and Deployment Instructions

## 1. Use Azure Cloud Shell for Commands

1. Click the `>_` icon in the top bar of the Azure Portal.
2. Cloud Shell is already signed in as `labtestuser45@gmail.com`.
3. Confirm the active account and subscription using:

```
az account show --query "{user:user.name,sub:name}" -o table
```

4. Run `deploy.sh`, `test-storage.sh`, and the other project scripts from Cloud Shell.

## 2. Allow Your PC's IP Address to Access Azure Storage

To access Azure Storage directly through your browser, you must allow your PC's public IPv4 address.

**Important:** The `storage-access.sh on` command previously executed in Cloud Shell added Cloud Shell's IP address, not your PC's IP address.

### Steps

1. On your PC, open [https://api.ipify.org](https://api.ipify.org).
2. Copy your public IPv4 address.
3. In Azure Cloud Shell, execute:

```
source env.sh

az storage account network-rule add \
  -g $RG \
  --account-name $STORAGE_NAME \
  --ip-address <your-pc-ipv4>
```

4. Make sure `./storage-access.sh on` was executed while signed in as `labtestuser45@gmail.com`.

   **Note:** The Reader roles are assigned to whichever account is logged in when the script runs.
5. Wait approximately 5 minutes for the firewall changes to take effect.
6. Open your Storage Account in Azure Portal.
7. Navigate to:
   - Containers
   - Queues
   - Tables
8. Select **Switch to Microsoft Entra user account**.

## 3. If the Azure Portal Still Shows "Not Authorized"

Your browser may be connecting to Azure Storage over IPv6 instead of IPv4.

Your error log shows an IP address starting with `2401:…`, which indicates an IPv6 address.

**Reason:** Azure Storage firewall IP network rules accept IPv4 addresses only.

### Recommended Solution

Use the application's built-in interface instead:

1. Open your application.
2. Navigate to **Admin → Azure Storage**.
3. Access the storage resources through the application backend.

The application backend reads the same Azure Storage resources:

- Blobs
- Queues
- Tables

This allows you to access Azure Storage without relying on direct browser access through the storage firewall.

Clarify which account runs each commandAdd a quick access verification step

### Option B: manual commands (what the script does)
```bash
ME=$(az ad signed-in-user show --query id -o tsv)
SCOPE=$(az storage account show -g $RG -n $STORAGE_NAME --query id -o tsv)

for R in "Storage Blob Data Reader" "Storage Queue Data Reader" "Storage Table Data Reader"; do
  az role assignment create --assignee-object-id $ME --assignee-principal-type User --role "$R" --scope $SCOPE -o none
done

MYIP=$(curl -s https://api.ipify.org)
az storage account update -g $RG -n $STORAGE_NAME --public-network-access Enabled --default-action Deny -o none
az storage account network-rule add -g $RG --account-name $STORAGE_NAME --ip-address $MYIP -o none
```
Verify:
```bash
az role assignment list --assignee $ME --scope $SCOPE --query "[].roleDefinitionName" -o tsv
az storage account show -g $RG -n $STORAGE_NAME --query "{public:publicNetworkAccess,keys:allowSharedKeyAccess,rules:networkRuleSet.ipRules[].ipAddressOrRange}" -o json
```
Expected: three Reader roles, `public: Enabled`, `keys: false`, and your IP listed.

> Public access is "Enabled" only with default action **Deny** plus your single IP. Everyone else stays blocked, and the backend keeps using its private endpoints.

## 2. Cross-check with the Azure CLI
All commands use `--auth-mode login` (your Entra identity, no keys).

```bash
A="--account-name $STORAGE_NAME --auth-mode login"
```

### 2.1 Blob Storage
```bash
# Product JSON files
az storage blob list $A -c products -o table
# Product images
az storage blob list $A -c product-images -o table
# Order archive
az storage blob list $A -c orders -o table
# Audit events (one JSON per event)
az storage blob list $A -c audit-logs --query "[].name" -o tsv
```
Read the content of one blob (replace the names):
```bash
az storage blob download $A -c products -n PROD-XXXXXXXX.json --file - 
az storage blob download $A -c orders   -n ORD-XXXXXXXXXX.json --file -
```
**Expected for the iPhone 8 product:** `product_name: iPhone 8`, `colour: Burgundy (Monochrome)`, `publication_status: Published`, `available_quantity: 9` (after one order), `image_blob_name` pointing to a blob that exists in `product-images`.

**Expected for the order:** `payment_method: COD`, `payment_status: Pending` (until you click *Cash collected*), `order_status: Delivered`, `delivery_status: Delivered`, a `delivered_at` timestamp and a `history` list showing Confirmed, Processing, Out for Delivery, Delivered.

Find specific audit events:
```bash
az storage blob list $A -c audit-logs --query "[?contains(name,'product_created') || contains(name,'cod_order_confirmed') || contains(name,'queue_message_processed') || contains(name,'delivery_completed')].name" -o tsv
```

### 2.2 Queue Storage
```bash
az storage queue list $A -o table
az storage message peek $A --queue-name quickkart-order-queue -o table
az storage message peek $A --queue-name quickkart-order-poison -o table
```
`peek` only looks; it does **not** remove or hide messages.
**Expected after the consumer ran and the order was delivered:** both queues empty. If you take a screenshot *before* running the consumer, you will see one message containing `order_id`, `product_id`, `customer_id`, `quantity`, `payment_method: COD`.

### 2.3 Table Storage
```bash
az storage entity query $A --table-name TableQueue   -o table
az storage entity query $A --table-name TableService -o table
```
Compact view:
```bash
az storage entity query $A --table-name TableService --query "items[].{Order:OrderID,Status:OrderStatus,Delivery:DeliveryStatus,Payment:PaymentStatus,Total:TotalAmount}" -o table
az storage entity query $A --table-name TableQueue   --query "items[].{Order:OrderID,Queue:QueueStatus,Dequeues:DequeueCount,Processed:ProcessedAt}" -o table
```
**Expected:** `TableQueue` row `QueueStatus: Processed` with a `ProcessedAt` time; `TableService` row `OrderStatus: Delivered`, `DeliveryStatus: Delivered`, `PaymentStatus: Pending` (or `Paid` if you confirmed cash).

### 2.4 One-shot version
```bash
./storage-access.sh check
```

## 3. Cross-check with the Azure Portal
1. Open https://portal.azure.com and go to **Resource groups -> rg-ecommerce-demo -> your storage account** (name starts with `ecom`).
2. **Blob data:** left menu **Data storage -> Containers**.
   - If you see "not authorized to perform this operation", click **Switch to Microsoft Entra user account** (shown above the list). Keys are disabled, so Entra login is required.
   - Open `products`, click a `PROD-...json` blob, then the **Edit** or **Preview** tab to read the JSON. Check colour, quantity, publication status, `image_blob_name`.
   - Open `product-images` and confirm the image blob named in that JSON exists (click it, then **Preview**).
   - Open `orders`, view `ORD-...json`: order, payment and delivery fields.
   - Open `audit-logs` and browse the year/month/day folders for `product_created`, `product_published`, `cod_order_confirmed`, `order_added_to_queue`, `queue_message_processed`, `delivery_completed`.
3. **Queue data:** **Data storage -> Queues -> quickkart-order-queue**. Messages show with their dequeue count. Open `quickkart-order-poison` too (empty unless you ran the failure demo).
4. **Table data:** **Data storage -> Tables -> TableQueue** and **TableService**. If the portal says it is not authorized, choose **Microsoft Entra user account** as the authentication method.
5. **Security settings to screenshot for the demo:**
   - **Security + networking -> Networking**: public network access, your temporary IP rule, and **Private endpoint connections** (blob, queue, table).
   - **Access Control (IAM) -> Role assignments**: the backend VMSS identity with Blob, Queue and Table Data Contributor.
   - **Settings -> Configuration**: *Allow storage account key access* = **Disabled**.

## 4. Cross-check with VS Code (optional)
1. Install the **Azure Resources** and **Azure Storage** extensions and sign in.
2. Azure panel -> Storage Accounts -> your account -> Blob Containers. Click a blob to open the JSON.
3. If your extension version does not list Queues or Tables, use **Azure Storage Explorer** (desktop, sign in with Entra) or the CLI commands above.

## 5. Compare with the application
| App screen (Admin Dashboard) | Storage location | Must match |
|---|---|---|
| Table Service | `TableService` table | order id, statuses, total |
| Table Queue | `TableQueue` table | queue status, processed time |
| Messages waiting | `quickkart-order-queue` | same message count |
| Poison queue count | `quickkart-order-poison` | same count |
| Blob list (orders, audit) | `orders`, `audit-logs` containers | same blob names |
| Seller portal stock | `products/PROD-...json` | `available_quantity` |

## 6. Optional extra checks
- **Duplicate order safety:** open the checkout page, double-click *Confirm Order* or refresh. Only **one** `ORD-...json` should exist and stock should drop by one.
- **Inventory ledger:** in the product JSON, `reserved_orders` lists the order ids that took stock.
- **No keys in use:** `az storage account show -g $RG -n $STORAGE_NAME --query allowSharedKeyAccess` returns `false`.

## 7. Close access again (do not skip)
```bash
./storage-access.sh off
```
Manual version:
```bash
MYIP=$(curl -s https://api.ipify.org)
az storage account network-rule remove -g $RG --account-name $STORAGE_NAME --ip-address $MYIP -o none
az storage account update -g $RG -n $STORAGE_NAME --public-network-access Disabled -o none
for R in "Storage Blob Data Reader" "Storage Queue Data Reader" "Storage Table Data Reader"; do
  az role assignment delete --assignee $ME --role "$R" --scope $SCOPE
done
```
Verify:
```bash
az storage account show -g $RG -n $STORAGE_NAME --query publicNetworkAccess -o tsv   # Disabled
curl -s http://<frontend-ip>/api/health?deep=1                                      # still status ok
```

## 8. Troubleshooting
| Problem | Cause | Fix |
|---|---|---|
| `AuthorizationFailure` / "not authorized" in portal or CLI | firewall or role not propagated yet, or your IP changed | wait 5 min; rerun `./storage-access.sh on` |
| `AuthorizationPermissionMismatch` | missing Reader role | rerun step 1 and wait |
| Portal list empty / "Switch to Entra" shown | key access disabled | click *Switch to Microsoft Entra user account* |
| `az storage entity query` unknown option | old Azure CLI | `az upgrade` |
| Path errors in Git Bash | MSYS path conversion | `export MSYS_NO_PATHCONV=1` (already in `env.sh`) |