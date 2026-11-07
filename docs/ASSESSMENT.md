# Implementation Assessment (done BEFORE coding)
Repository inspected: Phase-1 "azure-ecommerce-demo" (Flask + Bootstrap, Bicep, 2 VMSS, Blob via Managed Identity).

| Area | Finding | Status |
|---|---|---|
| Frontend | Bootstrap 5 + vanilla JS, nginx on frontend VMSS, `/api` reverse proxy | Implemented (kept) |
| Backend | Flask + gunicorn, blueprints, `DefaultAzureCredential` | Implemented (kept, extended) |
| Storage | Blob only: products, product-images, orders, audit-logs, application-backups | Implemented |
| Managed Identity / RBAC | System-assigned MI, **Blob** Data Contributor only | Partial -> Queue + Table roles added |
| Networking | VNet, 3 subnets, ASG, NSG, NAT, private endpoint + DNS for **blob only** | Partial -> queue + table PEs/DNS added |
| Autoscaling / LB | Both VMSS 1/2/4, public + internal LB | Implemented (kept) |
| Seller authentication | none | **Missing** -> added |
| Customer authentication | none | **Missing** -> added |
| Roles / authorization | none (all APIs open) | **Missing** -> seller / customer / admin |
| Product management | CRUD without owner, status, colour, publish flow | Partial -> rewritten model (spec JSON) |
| Cart / checkout / COD | client-side cart, generic orders without COD flow | Partial -> server cart, COD checkout |
| Order service | stock decrement, no idempotency, price from DB only | Partial -> idempotent, outbox, ETag ledger |
| Queue service | none | **Missing** -> `quickkart-order-queue` + poison queue + consumer |
| TableQueue / TableService | none | **Missing** -> Azure Table Storage |
| Delivery service | none | **Missing** -> lifecycle + admin API |
| Dashboards | storage explorer only | Partial -> admin/seller/customer dashboards |
| Audit logging | free-form events | Partial -> normalized schema (event id/type/entity/actor/result) |
| Broken | Phase-1 `test-storage.sh accept` assumed open APIs | Replaced by `e2e_test.py` |

**Dependencies:** Auth -> every protected route; Product model -> cart/order/home; Order service -> Queue + Tables + Blob; Consumer -> Tables; Delivery -> Tables + Blob; Bicep (queues/tables/PEs/roles) -> backend startup.

**Storage mapping decision:** no other database existed, so "Table Queue" and "Table Service" are implemented as Azure Table Storage tables `TableQueue` and `TableService` (as the brief allows). Blob = products/images/order archive/audit/delivery records/users/carts; Queue = async order messages; Table = operational rows.

**Known scope limits:** one product per order (cart holds many lines, checkout buys one line); no online payment (COD only); shared HTTP (no TLS) demo endpoint.
