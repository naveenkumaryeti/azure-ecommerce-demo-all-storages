"""Order lifecycle. Blob (order JSON) is the source of truth; TableService/TableQueue/Queue are derived and repaired by reconcile().
Blob, Queue and Table are SEPARATE services - there is no cross-service transaction. We use: deterministic order IDs (idempotency),
ETag writes, an idempotent inventory ledger (product.reserved_orders), an outbox flag, and reconciliation."""
import hashlib
import logging
from datetime import datetime, timezone

from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError

import config
from models import order as om
from models.product import now
from services import audit_service as audit
from services import blob_service as bs
from services import queue_service as qs
from services import table_service as ts
from services.errors import AppError

log = logging.getLogger(__name__)
P, O = config.CONTAINERS["products"], config.CONTAINERS["orders"]
QPK = config.ORDER_QUEUE
FLOW = ["Confirmed", "Processing", "Out for Delivery", "Delivered"]
DELIVERY = {"Confirmed": "Pending", "Processing": "Processing", "Out for Delivery": "Out for Delivery", "Delivered": "Delivered"}


def _retry(fn, tries=6):
    for _ in range(tries):
        try:
            return fn()
        except HttpResponseError as e:
            if e.status_code != 412:
                raise
    raise AppError("Resource is busy, please retry", 409, "CONFLICT")


def mutate_order(oid, fn):
    """Read-modify-write the order JSON with an ETag guard."""
    def once():
        o, etag = bs.get_json(O, f"{oid}.json")
        fn(o)
        o["updated_at"] = now()
        bs.put_json(O, f"{oid}.json", o, etag=etag)
        return o
    return _retry(once)


def order_id_for(customer_id, key):
    return "ORD-" + hashlib.sha256(f"{customer_id}:{key}".encode()).hexdigest()[:10].upper()


def service_entity(o):
    return {"PartitionKey": o["customer_id"], "RowKey": o["order_id"], "OrderID": o["order_id"], "ProductID": o["product_id"],
            "ProductName": o["product_name"], "CustomerID": o["customer_id"], "SellerID": o["seller_id"], "Quantity": o["quantity"],
            "TotalAmount": o["total_amount"], "PaymentMethod": o["payment_method"], "OrderStatus": o["order_status"],
            "PaymentStatus": o["payment_status"], "DeliveryStatus": o["delivery_status"], "CreatedAt": o["created_at"],
            "UpdatedAt": o["updated_at"], "DeliveredAt": o.get("delivered_at", "")}


def sync_service_row(o):
    ts.upsert(config.TABLE_SERVICE, service_entity(o))


def message(o):
    return {"order_id": o["order_id"], "product_id": o["product_id"], "customer_id": o["customer_id"], "quantity": o["quantity"],
            "payment_method": o["payment_method"], "order_status": "Confirmed", "order_timestamp": o["created_at"]}


def apply_inventory(o):
    """Idempotent: product.reserved_orders remembers which orders already decremented stock."""
    oid, pid, qty = o["order_id"], o["product_id"], o["quantity"]

    def once():
        p, etag = bs.get_json(P, f"{pid}.json")
        if oid in p.get("reserved_orders", []):
            return
        if p["available_quantity"] < qty:
            raise AppError(f"Only {p['available_quantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")
        p["available_quantity"] -= qty
        p["reserved_orders"] = (p.get("reserved_orders", []) + [oid])[-100:]
        if p["available_quantity"] == 0 and p["publication_status"] == "Published":
            p["publication_status"] = "Out of Stock"
        p["updated_at"] = now()
        bs.put_json(P, f"{pid}.json", p, etag=etag)
    _retry(once)


def run_outbox(oid):
    """Create TableService + TableQueue rows and enqueue the message. Safe to repeat (consumer is idempotent)."""
    o, _ = bs.get_json(O, f"{oid}.json")
    if not o["outbox_pending"]:
        return o
    sync_service_row(o)
    if not ts.get(config.TABLE_QUEUE, QPK, oid):
        ts.upsert(config.TABLE_QUEUE, {"PartitionKey": QPK, "RowKey": oid, "OrderID": oid, "ProductID": o["product_id"],
                                       "CustomerID": o["customer_id"], "Quantity": o["quantity"], "PaymentMethod": o["payment_method"],
                                       "QueueStatus": "Queued", "DequeueCount": 0, "CreatedAt": now(), "ProcessedAt": ""})
    qs.send(config.ORDER_QUEUE, message(o))
    o = mutate_order(oid, lambda x: x.update(outbox_pending=False))
    audit.log_event("order_added_to_queue", oid, o["customer_id"])
    return o


def create_order(customer, data, key):
    pid, address = str(data.get("product_id", "")), str(data.get("delivery_address", "")).strip()
    try:
        qty = int(data.get("quantity"))
    except (TypeError, ValueError):
        raise AppError("quantity must be a whole number")
    if data.get("payment_method", "COD") != "COD":
        raise AppError("only Cash on Delivery (COD) is supported")
    if len(address) < 10:
        raise AppError("a delivery address (at least 10 characters) is required")
    if qty < 1:
        raise AppError("quantity must be at least 1")
    oid = order_id_for(customer["uid"], key)
    try:                                      # duplicate submission -> return the original order, change nothing
        existing, _ = bs.get_json(O, f"{oid}.json")
        return existing, False
    except ResourceNotFoundError:
        pass
    try:
        prod, _ = bs.get_json(P, f"{pid}.json")
    except (ResourceNotFoundError, HttpResponseError):
        raise AppError("invalid product id")
    if prod.get("publication_status") != "Published":
        raise AppError("this product is not available for purchase", 409, "NOT_AVAILABLE")
    if qty > prod["available_quantity"]:
        raise AppError(f"Only {prod['available_quantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")
    order = om.build(oid, customer, prod, qty, address)        # price/total/seller from storage, not from the browser
    try:
        bs.put_json(O, f"{oid}.json", order, create_only=True)
    except ResourceExistsError:               # concurrent duplicate
        existing, _ = bs.get_json(O, f"{oid}.json")
        return existing, False
    try:
        apply_inventory(order)
    except AppError:
        bs.delete(O, f"{oid}.json")           # we just created it and stock was not reserved: undo
        raise
    order = mutate_order(oid, lambda x: x.update(inventory_applied=True))
    audit.log_event("cod_order_confirmed", oid, customer["uid"], details={"product_id": pid, "quantity": qty})
    try:
        order = run_outbox(oid)
    except Exception as e:                    # order is safe in Blob; reconcile() will finish the queue step
        log.error("outbox failed for %s: %s", oid, e)
        audit.log_event("order_queue_failed", oid, customer["uid"], "failure", {"error": str(e)[:200]})
    return order, True


def public_order(o):
    return {**o, "queue_status": "Retrying" if o.get("outbox_pending") else "Queued",
            "message": "Your order has been successfully placed!"}


def update_delivery(oid, new, actor):
    if new not in FLOW[1:]:
        raise AppError("status must be Processing, Out for Delivery or Delivered")

    def f(o):
        cur = o["order_status"]
        if cur == new and new != "Delivered":
            return
        if FLOW.index(new) != FLOW.index(cur) + 1:
            raise AppError(f"cannot move order from {cur} to {new}", 409, "INVALID_TRANSITION")
        o["order_status"], o["delivery_status"] = new, DELIVERY[new]
        if new == "Delivered":
            o["delivered_at"] = now()
        o["history"].append({"status": new, "at": now(), "by": actor})
    try:
        o = mutate_order(oid, f)
    except ResourceNotFoundError:
        raise AppError("order not found", 404, "NOT_FOUND")
    sync_service_row(o)
    audit.log_event("delivery_completed" if new == "Delivered" else "order_status_updated", oid, actor, details={"status": new})
    return o


def confirm_cash(oid, actor):
    def f(o):
        if o["order_status"] not in ("Out for Delivery", "Delivered"):
            raise AppError("cash can only be confirmed once the order is out for delivery or delivered", 409, "INVALID_TRANSITION")
        if o["payment_status"] != "Paid":
            o["payment_status"], o["paid_at"] = "Paid", now()
    try:
        o = mutate_order(oid, f)
    except ResourceNotFoundError:
        raise AppError("order not found", 404, "NOT_FOUND")
    sync_service_row(o)
    audit.log_event("cod_payment_collected", oid, actor)
    return o


def reconcile():
    """Repair cross-service drift using the order blobs as truth."""
    fixed = []
    for b in bs.list_blobs(O):
        o, _ = bs.get_json(O, b["name"])
        oid = o["order_id"]
        try:
            if not o["inventory_applied"]:
                try:
                    apply_inventory(o)
                    o = mutate_order(oid, lambda x: x.update(inventory_applied=True))
                    fixed.append(f"{oid}: inventory applied")
                except AppError:
                    o = mutate_order(oid, lambda x: x.update(order_status="Cancelled", delivery_status="Cancelled", outbox_pending=False))
                    fixed.append(f"{oid}: cancelled (no stock)")
            if o["outbox_pending"] and o["inventory_applied"]:
                o = run_outbox(oid)
                fixed.append(f"{oid}: queued")
            row = ts.get(config.TABLE_SERVICE, o["customer_id"], oid)
            if not row or (row["OrderStatus"], row["PaymentStatus"]) != (o["order_status"], o["payment_status"]):
                sync_service_row(o)
                fixed.append(f"{oid}: TableService synced")
        except Exception as e:
            log.error("reconcile %s failed: %s", oid, e)
            fixed.append(f"{oid}: FAILED {e}")
    return fixed


def overview(seller_id=None):
    rows = ts.list_all(config.TABLE_SERVICE)
    if seller_id:
        rows = [r for r in rows if r.get("SellerID") == seller_id]
    c = lambda s: sum(1 for r in rows if r["OrderStatus"] == s)
    return {"total": len(rows), "confirmed": c("Confirmed"), "processing": c("Processing"), "out_for_delivery": c("Out for Delivery"),
            "delivered": c("Delivered"), "pending_cod_payments": sum(1 for r in rows if r["PaymentMethod"] == "COD" and r["PaymentStatus"] == "Pending"),
            "orders": sorted(rows, key=lambda r: r["CreatedAt"], reverse=True)}


def queue_overview():
    rows = ts.list_all(config.TABLE_QUEUE)
    s = lambda k: sum(1 for r in rows if r["QueueStatus"] == k)
    return {"queue": config.ORDER_QUEUE, "approximate_messages": qs.count(config.ORDER_QUEUE), "poison_messages": qs.count(config.POISON_QUEUE),
            "stats": {"total": len(rows), "pending": s("Queued"), "processed": s("Processed"), "failed": s("Failed"),
                      "retries": sum(max(int(r.get("DequeueCount", 0)) - 1, 0) for r in rows)},
            "messages": qs.peek(config.ORDER_QUEUE, 20)}
