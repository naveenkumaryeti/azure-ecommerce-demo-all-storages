# QuickKart Final Demo - 28 steps (Cloud Technet)
Setup: `cd scripts && source env.sh && IP=$(fe_ip) && cat .state/credentials.env`. Browser: `http://$IP` (HTTP, not https). Keep the consumer worker OFF (`./configure-worker.sh stop`) so the message stays visible in step 19.

| # | Step | Where / command | Expected |
|---|---|---|---|
| 1 | Show infrastructure | Portal -> resource group `rg-ecommerce-demo`; `az resource list -g $RG -o table` | VMSS x2, LBs, VNet, NSG/ASG, storage, 3 private endpoints |
| 2 | Open Seller Portal | `http://$IP/login.html` | login page |
| 3 | Seller login | `seller@quickkart.demo` + password from credentials file | redirected to Product Management |
| 4 | Product Management | page header | empty list |
| 5 | Add iPhone 8 | **Add New Product** (button "Fill iPhone 8 demo values" fills name/colour/status/qty) | form open |
| 6 | Colour | `Burgundy (Monochrome)` | |
| 7 | Quantity | `10` | |
| 8 | Price | enter **your** selling price (never defaulted) | |
| 9 | Image | choose a JPG/PNG/WebP | preview shown; Save -> status **Draft** |
| 10 | Publish | **Publish** button (fails if price/image missing - show the error once) | status **Published** |
| 11 | Blob proof | Portal/Admin -> Azure Storage -> `products/PROD-xxxx.json`, `product-images/PROD-xxxx.png`, `audit-logs/...product_created...` | JSON has colour, 10, `image_blob_name` |
| 12 | Home page | `http://$IP/` (no login) | iPhone 8 card: image, colour, "Recently Launched", price, stock, View Product, Add to Cart |
| 13 | Customer login | `customer@quickkart.demo` | |
| 14 | Add to cart | **View Product** -> Add to Cart -> Cart | line shown |
| 15 | Checkout | Cart -> **Checkout** | summary: product, image, colour, unit price, qty, total |
| 16 | COD | radio "Cash on Delivery" (only option) | no card form |
| 17 | Confirm | enter address -> **Confirm Order** | |
| 18 | Confirmation | "Your order has been successfully placed!" | Order ID, date, qty, total, COD, **Confirmed** |
| 19 | Queue Storage | Portal -> storage -> Queues -> `quickkart-order-queue` (needs temporary access, see README) **or** Admin Dashboard "Messages waiting" | 1 message, dequeue count 0 |
| 20 | TableQueue | Admin Dashboard -> TableQueue | row **Queued** |
| 21 | TableService | Admin Dashboard -> TableService | row Confirmed / Pending |
| 22 | Run consumer | **Run queue consumer** (optionally first **simulate failure** twice to show dequeue count 1,2 and retries) | TableQueue **Processed**, TableService **Processing** |
| 23 | Delivery | admin: **-> Out for Delivery**, then **-> Delivered** (try skipping a step: rejected) | Delivered |
| 24 | TableService | refresh | OrderStatus/DeliveryStatus Delivered; payment still **Pending**; customer "My Orders" shows the same |
| 25 | Blob proof | Azure Storage -> `orders/ORD-xxxx.json` (`delivered_at`, history) and `audit-logs/...delivery_completed...` | present |
| 26 | MI + RBAC | `./configure-rbac.sh show`; Portal -> storage -> IAM | Blob + Queue + Table Data Contributor for `backend-vmss` |
| 27 | NSG/ASG | `az network nsg rule list -g $RG --nsg-name nsg-backend -o table` | 5000 only from asg-frontend |
| 28 | VMSS | `./configure-vmss.sh status`; Portal -> backend-vmss -> Scaling | 2 instances, min1/def2/max4 |
Bonus: **Cash collected** button (payment Paid), duplicate-order demo (browser refresh on checkout), `./configure-rbac.sh remove` with `ROLE="Storage Queue Data Contributor"` -> orders still saved but queue step retries (then `add` and press Reconcile).
Automated check of the whole flow: `./test-storage.sh accept`.
