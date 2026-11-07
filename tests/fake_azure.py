"""In-memory stand-ins for Blob/Queue/Table used ONLY by `e2e_test.py --local` (offline logic check). Real tests use Azure."""
import json
from datetime import datetime, timezone

from azure.core.exceptions import HttpResponseError, ResourceExistsError, ResourceNotFoundError


def patch():
    from services import blob_service as bs, queue_service as qs, table_service as ts
    store, ver = {}, [0]

    def etag():
        ver[0] += 1
        return f'"0x{ver[0]}"'

    def put_json(c, n, obj, etag_=None, create_only=False, **kw):
        etag_ = kw.get("etag", etag_) if "etag" in kw else etag_
        cur = store.get((c, n))
        if create_only and cur:
            raise ResourceExistsError("exists")
        if etag_ and (not cur or cur["etag"] != etag_):
            e = HttpResponseError("precondition failed"); e.status_code = 412; raise e
        e_ = etag(); store[(c, n)] = {"data": json.dumps(obj).encode(), "ctype": "application/json", "etag": e_, "lm": datetime.now(timezone.utc)}
        return e_

    def get_json(c, n):
        if (c, n) not in store:
            raise ResourceNotFoundError("nf")
        r = store[(c, n)]; return json.loads(r["data"]), r["etag"]

    def upload_blob(c, n, data, ctype):
        store[(c, n)] = {"data": data, "ctype": ctype, "etag": etag(), "lm": datetime.now(timezone.utc)}

    def delete(c, n, etag=None):
        if (c, n) not in store:
            raise ResourceNotFoundError("nf")
        del store[(c, n)]

    def download(c, n):
        if (c, n) not in store:
            raise ResourceNotFoundError("nf")
        return store[(c, n)]["data"], store[(c, n)]["ctype"]

    def list_blobs(c):
        return [{"name": n, "size": len(r["data"]), "content_type": r["ctype"], "last_modified": r["lm"].isoformat(), "etag": r["etag"]}
                for (cc, n), r in sorted(store.items()) if cc == c]

    bs.put_json, bs.get_json, bs.upload_blob, bs.delete, bs.download, bs.list_blobs = put_json, get_json, upload_blob, delete, download, list_blobs
    bs.list_json = lambda c: [get_json(c, b["name"]) for b in list_blobs(c) if b["name"].endswith(".json")]
    bs.ensure_containers = lambda: None
    bs.list_containers = lambda: sorted({c for c, _ in store})
    bs.stats = lambda: ({k: len(list_blobs(v)) for k, v in {"products": "products", "images": "product-images", "orders": "orders", "audit": "audit-logs"}.items()}, None)

    class Msg:
        def __init__(s, i, body): s.id, s.pop_receipt, s.content, s.dequeue_count, s.inserted_on = f"m{i}", "r", body, 0, "now"
    queues, mid = {}, [0]

    def send(n, obj):
        mid[0] += 1; queues.setdefault(n, []).append(Msg(mid[0], json.dumps(obj)))

    def receive(n, mx=10, vis=0):
        out = queues.get(n, [])[:mx]
        for m in out: m.dequeue_count += 1
        return list(out)

    qs.ensure = lambda: None
    qs.send, qs.receive = send, receive
    qs.delete = lambda n, m: queues[n].remove(m)
    qs.peek = lambda n, k=20: [{"id": m.id, "dequeue_count": m.dequeue_count, "inserted_on": "now", "content": json.loads(m.content)} for m in queues.get(n, [])[:k]]
    qs.count = lambda n: len(queues.get(n, []))

    tables = {}
    ts.ensure = lambda: None

    def upsert(n, e):
        row = tables.setdefault(n, {}).setdefault((e["PartitionKey"], e["RowKey"]), {}); row.update(e)

    ts.upsert = upsert
    ts.get = lambda n, pk, rk: dict(tables.get(n, {}).get((pk, rk))) if (pk, rk) in tables.get(n, {}) else None
    ts.list_all = lambda n: [dict(v) for v in tables.get(n, {}).values()]
    ts.list_pk = lambda n, pk: [dict(v) for (p, _), v in tables.get(n, {}).items() if p == pk]
