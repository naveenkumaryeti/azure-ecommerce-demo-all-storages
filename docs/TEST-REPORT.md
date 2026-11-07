# End-to-End Testing Report

## What was executed
| Run | Environment | Result |
|---|---|---|
| `python3 scripts/e2e_test.py --local` | Flask app + **in-memory fakes** for Blob/Queue/Table (offline) | **27 / 27 PASS** (output below) |
| `./scripts/test-storage.sh accept` | **Real Azure deployment** | **Not run by the author of this package** - run it after `deploy.sh`; it must print PASS for all tests |

Honest scope: the offline run proves business logic (auth, roles, publish rules, server-side pricing, ETag/idempotency, stock, queue retries, poison queue, delivery rules, COD stays Pending). It does **not** prove Azure behaviour (Managed Identity tokens, RBAC, private endpoints/DNS, Bicep deployment). Those are covered by the Azure run and the infra checks at the end of `test-storage.sh`. Bicep files were not compiled in the authoring environment - `az deployment` will validate them.

## Test matrix
| # | Test | Verified by |
|---|---|---|
| 1-4 | Seller login, add iPhone 8, colour, stock 10 | API responses |
| 5-6 | Image + product JSON in Blob | admin storage listing (real blob names) |
| 7 | Publish -> on home API (hidden while Draft; publish without price rejected) | `GET /api/products` unauthenticated |
| 8-11 | Customer login, product view, cart, COD available | API |
| 12-13 | Unique Order ID; browser-sent price ignored; stock 10 -> 9 | API |
| 14-16 | Queue message, TableQueue row, TableService row | admin APIs |
| 17 | Consumer: TableQueue Processed, TableService Processing | admin APIs |
| 18-19 | Delivery lifecycle (skip rejected); Blob order JSON + delivery audit event | Blob read via API |
| 20 | COD payment Pending after delivery (+ Paid only after cash confirmation) | order JSON |
| 21-22 | Duplicate submit, over-stock, invalid product | status codes + stock |
| X1-X3 | RBAC 401/403, retries -> poison queue, reconcile | API |

## Offline run output
```
== QuickKart Phase 2 acceptance tests
  PASS  TEST  1 - Seller login
  PASS  TEST  2 - Add iPhone 8 (draft created)
  PASS  TEST  3 - Colour = Burgundy (Monochrome)
  PASS  TEST  4 - Stock = 10 units
  PASS  TEST  5 - Image uploaded to product-images
  PASS  TEST  6 - Product JSON in products container
  PASS  TEST  7 - Publish -> appears on homepage API (draft was hidden before)
  PASS  TEST 7.1 - Publishing without price is rejected
  PASS  TEST  8 - Customer login
  PASS  TEST  9 - Customer sees product name + price
  PASS  TEST 10 - Add to cart
  PASS  TEST 11 - COD option available
  PASS  TEST 12 - Order confirmed, unique Order ID (browser price ignored)
  PASS  TEST 13 - Stock 10 -> 9
  PASS  TEST 14 - Message in quickkart-order-queue
  PASS  TEST 15 - Order in TableQueue (Queued)
  PASS  TEST 16 - Order in TableService
  PASS  TEST 17 - Consumer processes message (TableQueue=Processed, TableService=Processing)
  PASS  TEST 18 - Delivery Confirmed->Processing->Out for Delivery->Delivered (skipping steps rejected)
  PASS  TEST 19 - Blob order JSON = Delivered + delivery audit event stored
  PASS  TEST 20 - COD payment still Pending after delivery
  PASS  TEST 20.1 - Cash collection confirmation -> Paid
  PASS  TEST 21 - Duplicate submission: same order, stock not decremented twice
  PASS  TEST 22 - Cannot order more than stock / invalid product rejected
  PASS  TEST X1 - Customer cannot call admin APIs (403) / anonymous gets 401
  PASS  TEST X2 - Retries then poison queue (dequeue_count>3 -> poison, TableQueue=Failed)
  PASS  TEST X3 - Reconcile endpoint runs
== PASSED 27/27
```
