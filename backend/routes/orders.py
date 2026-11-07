import uuid

from azure.core.exceptions import ResourceNotFoundError
from flask import Blueprint, g, jsonify, request

from routes.cart import remove_line
from services import auth_service as auth
from services import blob_service as bs
from services import order_service as osv
from services import queue_worker
from services import table_service as ts
from services.errors import AppError
import config

bp = Blueprint("orders", __name__)


@bp.get("/api/payment-methods")
def payment_methods():
    return jsonify([{"code": "COD", "label": "Cash on Delivery", "offline": True}])


@bp.post("/api/orders")
@auth.require("customer")
def create():
    key = request.headers.get("Idempotency-Key") or uuid.uuid4().hex   # frontend sends one key per checkout attempt
    order, created = osv.create_order(g.user, request.get_json(silent=True) or {}, key)
    if created:
        remove_line(g.user["uid"], order["product_id"])
    return jsonify({**osv.public_order(order), "duplicate": not created}), 201 if created else 200


def _get(oid):
    try:
        return bs.get_json(osv.O, f"{oid}.json")[0]
    except ResourceNotFoundError:
        raise AppError("order not found", 404, "NOT_FOUND")


@bp.get("/api/orders/<oid>")
@auth.require("customer", "seller", "admin")
def get_order(oid):
    o, u = _get(oid), g.user
    if (u["role"] == "customer" and o["customer_id"] != u["uid"]) or (u["role"] == "seller" and o["seller_id"] != u["uid"]):
        raise AppError("not your order", 403, "FORBIDDEN")
    return jsonify(o)


@bp.get("/api/customer/orders")
@auth.require("customer")
def my_orders():
    rows = ts.list_pk(config.TABLE_SERVICE, g.user["uid"])
    return jsonify(sorted(rows, key=lambda r: r["CreatedAt"], reverse=True))


@bp.post("/api/orders/<oid>/process")
@auth.require("admin")
def process_one(oid):
    o = _get(oid)
    return jsonify({"order_id": oid, "result": queue_worker.process_order_message(osv.message(o))})
