from flask import Blueprint, g, jsonify, request

import config
from services import auth_service as auth
from services import blob_service as bs
from services import order_service as osv
from services import queue_worker
from services import table_service as ts
from services.errors import AppError

bp = Blueprint("admin", __name__)


@bp.get("/api/admin/orders")
@auth.require("admin", "seller")
def orders():
    return jsonify(osv.overview(g.user["uid"] if g.user["role"] == "seller" else None))


@bp.get("/api/admin/queue")
@auth.require("admin")
def queue():
    return jsonify(osv.queue_overview())


@bp.post("/api/admin/queue/run")
@auth.require("admin")
def run_consumer():
    return jsonify({"results": queue_worker.process_batch(fail=request.args.get("fail") == "1")})


@bp.post("/api/admin/reconcile")
@auth.require("admin")
def reconcile():
    return jsonify({"fixed": osv.reconcile()})


@bp.put("/api/admin/orders/<oid>/delivery-status")
@auth.require("admin")
def delivery(oid):
    st = (request.get_json(silent=True) or {}).get("status", "")
    return jsonify(osv.update_delivery(oid, st, g.user["uid"]))


@bp.post("/api/admin/orders/<oid>/confirm-cash")
@auth.require("admin")
def cash(oid):
    return jsonify(osv.confirm_cash(oid, g.user["uid"]))


@bp.get("/api/admin/table-queue")
@auth.require("admin")
def table_queue():
    return jsonify(sorted(ts.list_all(config.TABLE_QUEUE), key=lambda r: r["CreatedAt"], reverse=True))


@bp.get("/api/admin/table-service")
@auth.require("admin")
def table_service():
    return jsonify(sorted(ts.list_all(config.TABLE_SERVICE), key=lambda r: r["CreatedAt"], reverse=True))


@bp.get("/api/admin/storage/containers")
@auth.require("admin")
def containers():
    return jsonify([c for c in bs.list_containers() if c not in config.HIDDEN_CONTAINERS])


@bp.get("/api/admin/storage/products")
@auth.require("admin")
def st_products():
    return jsonify({"products": bs.list_blobs(config.CONTAINERS["products"]), "product-images": bs.list_blobs(config.CONTAINERS["images"])})


@bp.get("/api/admin/storage/orders")
@auth.require("admin")
def st_orders():
    return jsonify({"orders": bs.list_blobs(config.CONTAINERS["orders"]), "audit-logs": bs.list_blobs(config.CONTAINERS["audit"])})
