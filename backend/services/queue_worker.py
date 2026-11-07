"""Queue consumer: validate -> process -> update records -> delete message ONLY after success.
Failures are left on the queue (reappear after the visibility timeout = retry). After MAX_DEQUEUE attempts -> poison queue."""
import json
import logging

import config
from models.product import now
from services import audit_service as audit
from services import blob_service as bs
from services import queue_service as qs
from services import table_service as ts
from services.errors import AppError
from services import order_service as osv

log = logging.getLogger(__name__)


def process_order_message(body):
    for k in ("order_id", "product_id", "customer_id", "quantity"):
        if k not in body:
            raise AppError(f"invalid message: missing {k}")
    oid = body["order_id"]
    row = ts.get(config.TABLE_QUEUE, osv.QPK, oid)
    if row and row.get("QueueStatus") == "Processed":
        return "duplicate (already processed)"
    order, _ = bs.get_json(osv.O, f"{oid}.json")
    if order["customer_id"] != body["customer_id"] or order["product_id"] != body["product_id"]:
        raise AppError("message does not match the stored order")

    def f(o):
        if o["order_status"] == "Confirmed":
            o["order_status"], o["delivery_status"] = "Processing", "Processing"
            o["history"].append({"status": "Processing", "at": now(), "by": "queue-consumer"})
    order = osv.mutate_order(oid, f)
    ts.upsert(config.TABLE_QUEUE, {"PartitionKey": osv.QPK, "RowKey": oid, "QueueStatus": "Processed", "ProcessedAt": now(), "LastError": ""})
    osv.sync_service_row(order)
    audit.log_event("queue_message_processed", oid, "queue-consumer")
    return "processed"


def _poison(m, body, reason):
    qs.send(config.POISON_QUEUE, {"original": body, "reason": reason, "dequeue_count": m.dequeue_count})
    qs.delete(config.ORDER_QUEUE, m)
    if body.get("order_id"):
        ts.upsert(config.TABLE_QUEUE, {"PartitionKey": osv.QPK, "RowKey": body["order_id"], "QueueStatus": "Failed", "LastError": reason[:200]})
    audit.log_event("queue_message_poisoned", (body or {}).get("order_id", ""), "queue-consumer", "failure", {"reason": reason[:200]})


def process_batch(max_messages=10, fail=False):
    """fail=True is a TEACHING switch: it makes this run fail so students can watch dequeue_count and retries."""
    out = []
    for m in qs.receive(config.ORDER_QUEUE, max_messages, config.VISIBILITY_SECONDS):
        try:
            body = json.loads(m.content)
        except ValueError:
            _poison(m, {}, "unparseable message")
            out.append({"message_id": m.id, "result": "moved to poison queue (invalid JSON)"})
            continue
        if m.dequeue_count > config.MAX_DEQUEUE:
            _poison(m, body, f"exceeded {config.MAX_DEQUEUE} attempts")
            out.append({"order_id": body.get("order_id"), "dequeue_count": m.dequeue_count, "result": "moved to poison queue"})
            continue
        try:
            if fail:
                raise RuntimeError("simulated failure (teaching demo)")
            res = process_order_message(body)
            qs.delete(config.ORDER_QUEUE, m)
            out.append({"order_id": body["order_id"], "dequeue_count": m.dequeue_count, "result": res})
        except Exception as e:
            log.warning("processing %s failed (attempt %s): %s", body.get("order_id"), m.dequeue_count, e)
            try:
                ts.upsert(config.TABLE_QUEUE, {"PartitionKey": osv.QPK, "RowKey": body.get("order_id", m.id), "DequeueCount": m.dequeue_count, "LastError": str(e)[:200]})
            except Exception:
                pass
            out.append({"order_id": body.get("order_id"), "dequeue_count": m.dequeue_count, "result": f"failed, will retry after {config.VISIBILITY_SECONDS}s: {e}"})
    return out
