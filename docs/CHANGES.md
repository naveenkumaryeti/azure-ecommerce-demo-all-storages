# Changed files: what / why / how / test
| File | What changed | Why | How it works | Test |
|---|---|---|---|---|
| `backend/config.py` | queue/table names, endpoints, secrets from env, new containers | Phase-2 services | env-only config; random secret fallback for local | `e2e_test.py --local` |
| `services/errors.py` (new) | `AppError`, `AuthError` | uniform HTTP errors | handler in `app.py` maps to JSON | X1 |
| `services/auth_service.py` (new) | users in `users/` blobs, PBKDF2, signed 8 h tokens, `require(role)` | no auth existed | login -> token; decorator enforces roles; seeds demo users | tests 1, 8, X1 |
| `services/queue_service.py` (new) | Azure Queue wrapper (Managed Identity) | async order processing | send/receive/peek/delete/count | 14, 17 |
| `services/table_service.py` (new) | Azure Table wrapper | TableQueue/TableService | MERGE upserts, PK queries | 15, 16 |
| `services/order_service.py` (new) | COD orders, idempotency, ETag stock ledger, outbox, delivery, cash, reconcile | safe orders across separate stores | deterministic order id from `Idempotency-Key`; `product.reserved_orders` makes decrement idempotent; `outbox_pending` retried by `reconcile()` | 12, 13, 21, 22 |
| `services/queue_worker.py`, `worker.py` (new) | consumer, retries, poison queue, idempotent | requirement 7 | delete only after success; dequeue_count > max -> poison | 17, X2 |
| `services/audit_service.py` | event id/type/entity/actor/result schema | requirement 13 | one blob per event | 19 |
| `models/product.py`, `models/order.py` | spec JSON fields, statuses, publish rules | requirement 2/3 | price optional while Draft; publish needs price>0, stock, image | 2-7 |
| `routes/auth.py, cart.py, orders.py, admin.py` (new) / `products.py, storage.py` (rewritten) | all endpoints in the brief + role checks | requirement 11 | see `docs/API.md` | e2e |
| `app.py` | bootstrap (containers/queues/tables/seed), new error mapping | startup & errors | retries bootstrap every 30 s | health |
| `frontend/*` | login, home (published products), details, cart, checkout (COD), my orders, seller portal, admin dashboard, explorer with auth | requirements 2,4,5,10 | pages call `/api` with the token; nothing hard-coded | manual demo |
| `infrastructure/storage.bicep` | + queues, tables, `users`/`carts` containers, queue+table private endpoints & DNS zones | requirement 8/12 | loops over `blob/queue/table` | `az deployment` |
| `infrastructure/identity.bicep` | 3 role assignments (Blob/Queue/Table Data Contributor) | least privilege | account scope | `configure-rbac.sh show` |
| `scripts/deploy.sh` | secrets + seed passwords, worker unit, prints credentials | auth + queue | creds in `scripts/.state` | deploy |
| `scripts/e2e_test.py` (new), `test-storage.sh` | 22 acceptance tests + extras, infra checks | requirement 14 | stdlib HTTP client; `--local` uses fakes | run it |
| `scripts/configure-rbac.sh, configure-worker.sh, update-app.sh` | per-role RBAC demo, worker toggle, code push to live VMSS | demo/operations | `az vmss run-command` | each script |
