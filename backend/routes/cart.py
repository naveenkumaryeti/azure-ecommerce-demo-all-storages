"""Server-side cart: carts/<customer_id>.json"""
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from flask import Blueprint, g, jsonify, request

import config
from models.product import now
from services import audit_service as audit
from services import auth_service as auth
from services import blob_service as bs
from services.errors import AppError

bp = Blueprint("cart", __name__)
C, P = config.CONTAINERS["carts"], config.CONTAINERS["products"]


def load(uid):
    try:
        return bs.get_json(C, f"{uid}.json")
    except ResourceNotFoundError:
        return {"customer_id": uid, "items": []}, None


def save(cart, etag):
    cart["updated_at"] = now()
    bs.put_json(C, f"{cart['customer_id']}.json", cart, etag=etag, create_only=etag is None)


def modify(uid, fn):
    for _ in range(5):
        cart, etag = load(uid)
        fn(cart)
        try:
            save(cart, etag)
            return cart
        except HttpResponseError as e:
            if e.status_code != 412:
                raise
    raise AppError("cart busy, retry", 409, "CONFLICT")


def remove_line(uid, pid):
    modify(uid, lambda c: c.update(items=[i for i in c["items"] if i["product_id"] != pid]))


def _published(pid):
    try:
        p, _ = bs.get_json(P, f"{pid}.json")
    except (ResourceNotFoundError, HttpResponseError):
        raise AppError("invalid product id")
    if p.get("publication_status") != "Published":
        raise AppError("product is not available", 409, "NOT_AVAILABLE")
    return p


def view(cart):
    lines, total = [], 0.0
    for i in cart["items"]:
        try:
            p, _ = bs.get_json(P, f"{i['product_id']}.json")
        except Exception:  # noqa
            continue
        ok = p.get("publication_status") == "Published"
        sub = round((p.get("price") or 0) * i["quantity"], 2)
        total += sub if ok else 0
        lines.append({"product_id": p["product_id"], "product_name": p["product_name"], "colour": p.get("colour", ""),
                      "price": p.get("price"), "image_blob_name": p.get("image_blob_name", ""), "quantity": i["quantity"],
                      "available_quantity": p["available_quantity"], "available": ok, "subtotal": sub})
    return {"items": lines, "total": round(total, 2)}


@bp.get("/api/cart")
@auth.require("customer")
def get_cart():
    return jsonify(view(load(g.user["uid"])[0]))


@bp.post("/api/cart")
@auth.require("customer")
def add():
    d = request.get_json(silent=True) or {}
    pid = str(d.get("product_id", ""))
    try:
        qty = int(d.get("quantity", 1))
    except (TypeError, ValueError):
        raise AppError("quantity must be a number")
    p = _published(pid)

    def f(c):
        line = next((i for i in c["items"] if i["product_id"] == pid), None)
        new = (line["quantity"] if line else 0) + qty
        if qty < 1 or new > p["available_quantity"]:
            raise AppError(f"Only {p['available_quantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")
        if line:
            line["quantity"] = new
        else:
            c["items"].append({"product_id": pid, "quantity": qty})
    cart = modify(g.user["uid"], f)
    audit.log_event("product_added_to_cart", pid, g.user["uid"], details={"quantity": qty})
    return jsonify(view(cart)), 201


@bp.put("/api/cart/<pid>")
@auth.require("customer")
def set_qty(pid):
    try:
        qty = int((request.get_json(silent=True) or {}).get("quantity"))
    except (TypeError, ValueError):
        raise AppError("quantity must be a number")
    p = _published(pid)
    if qty > p["available_quantity"]:
        raise AppError(f"Only {p['available_quantity']} unit(s) in stock", 409, "INSUFFICIENT_STOCK")

    def f(c):
        c["items"] = [i for i in c["items"] if i["product_id"] != pid]
        if qty > 0:
            c["items"].append({"product_id": pid, "quantity": qty})
    return jsonify(view(modify(g.user["uid"], f)))


@bp.delete("/api/cart/<pid>")
@auth.require("customer")
def remove(pid):
    remove_line(g.user["uid"], pid)
    return jsonify(view(load(g.user["uid"])[0]))
