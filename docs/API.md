# API (JSON; `Authorization: Bearer <token>` from `/api/auth/login`)
| Method | Endpoint | Role | Notes |
|---|---|---|---|
| POST | `/api/auth/login` `/api/auth/register` | public | register = customer only |
| GET | `/api/auth/me` | any | |
| GET | `/api/products[?q=]` `/api/products/{id}` | public | **Published only** (home page source) |
| GET/POST | `/api/seller/products` | seller, admin | POST multipart: `product_name colour product_status available_quantity price category description image` |
| PUT/DELETE | `/api/seller/products/{id}` | owner seller, admin | PUT honours `If-Match` ETag (409 on conflict) |
| POST | `/api/seller/products/{id}/publish` `/unpublish` `/image` | owner seller, admin | publish needs price>0, stock>=1, image |
| GET/POST | `/api/cart` | customer | POST `{product_id, quantity}` |
| PUT/DELETE | `/api/cart/{product_id}` | customer | set quantity / remove |
| GET | `/api/payment-methods` | public | `COD` |
| POST | `/api/orders` | customer | body `{product_id, quantity, delivery_address, payment_method:"COD"}`, header `Idempotency-Key` (same key = same order). Price/total/seller are taken from storage |
| GET | `/api/orders/{id}` | owner, seller of product, admin | order JSON from Blob |
| GET | `/api/customer/orders` | customer | TableService rows |
| POST | `/api/orders/{id}/process` | admin | process that order's queue message now |
| GET | `/api/admin/orders` | admin, seller | summary counts + TableService rows (seller: own products) |
| GET | `/api/admin/queue` | admin | queue counts, TableQueue stats, peeked messages with dequeue_count |
| POST | `/api/admin/queue/run[?fail=1]` | admin | run consumer once (`fail=1` = teaching switch) |
| POST | `/api/admin/reconcile` | admin | repair Blob/Table/Queue drift |
| PUT | `/api/admin/orders/{id}/delivery-status` | admin | `{"status":"Processing\|Out for Delivery\|Delivered"}`, forward steps only |
| POST | `/api/admin/orders/{id}/confirm-cash` | admin | COD payment Pending -> Paid |
| GET | `/api/admin/table-queue` `/table-service` | admin | |
| GET | `/api/admin/storage/products` `/orders` `/containers` | admin | blob listings |
| GET/POST/DELETE | `/api/storage/*` | admin | dashboard + explorer (users container hidden) |
| GET | `/api/images/{blob}` | public | product images (served via backend) |
| GET | `/api/health[?deep=1]` | public | LB probe |
Errors: `{ "error": CODE, "message": text }` - 401 login, 403 role/RBAC, 409 stock/conflict/transition, 503 identity/network.
