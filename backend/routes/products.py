import re
from flask import Blueprint, g, jsonify, request

import config
from models import product as pm
from services import audit_service as audit
from services import auth_service as auth
from services import blob_service as bs
from services.errors import AppError

bp = Blueprint("products", __name__)
ID_RE = re.compile(r"^[A-Za-z0-9-]{3,40}$")
P, IMG = config.CONTAINERS["products"], config.CONTAINERS["images"]


def _name(pid):
    if not ID_RE.match(pid):
        raise AppError("invalid product id")
    return f"{pid}.json"


def _out(p, etag):
    return {**pm.public(p), "etag": etag}


def _own(p):
    if g.user["role"] != "admin" and p["seller_id"] != g.user["uid"]:
        raise AppError("this product belongs to another seller", 403, "FORBIDDEN")


def _input():
    return request.form.to_dict() if request.form else (request.get_json(silent=True) or {})


def _store_image(p, f):
    ctype = f.mimetype
    if ctype not in config.ALLOWED_IMAGE_TYPES:
        raise AppError("only JPG, PNG and WebP images are allowed")
    data = f.read(config.MAX_IMAGE_BYTES + 1)
    if len(data) > config.MAX_IMAGE_BYTES:
        raise AppError("image larger than 5 MB")
    ok = ((ctype == "image/jpeg" and data[:3] == b"\xff\xd8\xff") or (ctype == "image/png" and data[:4] == b"\x89PNG") or
          (ctype == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
    if not ok:
        raise AppError("file content does not match its image type")
    name = f"{p['product_id']}.{config.ALLOWED_IMAGE_TYPES[ctype]}"
    bs.upload_blob(IMG, name, data, ctype)
    old = p.get("image_blob_name")
    if old and old != name:
        try:
            bs.delete(IMG, old)
        except Exception:  # noqa
            pass
    p["image_blob_name"] = name
    audit.log_event("product_image_uploaded", p["product_id"], g.user["uid"], details={"image": name})


# ---------- public / customer ----------
@bp.get("/api/products")
def list_published():
    q = request.args.get("q", "").lower()
    items = [_out(d, e) for d, e in bs.list_json(P) if d.get("publication_status") == "Published"]
    items = [p for p in items if q in (p["product_name"] + p["colour"] + p["category"]).lower()]
    return jsonify(sorted(items, key=lambda p: p["created_at"], reverse=True))


@bp.get("/api/products/<pid>")
def get_published(pid):
    p, e = bs.get_json(P, _name(pid))
    if p.get("publication_status") != "Published":
        raise AppError("product not found", 404, "NOT_FOUND")
    return jsonify(_out(p, e))


# ---------- seller ----------
@bp.get("/api/seller/products")
@auth.require("seller", "admin")
def seller_list():
    items = [_out(d, e) for d, e in bs.list_json(P) if g.user["role"] == "admin" or d["seller_id"] == g.user["uid"]]
    return jsonify(sorted(items, key=lambda p: p["created_at"], reverse=True))


@bp.post("/api/seller/products")
@auth.require("seller", "admin")
def seller_create():
    p = pm.build(_input(), g.user["uid"])
    if request.files.get("image"):
        _store_image(p, request.files["image"])
    etag = bs.put_json(P, _name(p["product_id"]), p, create_only=True)
    audit.log_event("product_created", p["product_id"], g.user["uid"])
    return jsonify(_out(p, etag)), 201


@bp.put("/api/seller/products/<pid>")
@auth.require("seller", "admin")
def seller_update(pid):
    existing, current = bs.get_json(P, _name(pid))
    _own(existing)
    p = pm.build(_input(), existing["seller_id"], existing)
    if request.files.get("image"):
        _store_image(p, request.files["image"])
    if p["publication_status"] == "Published" and pm.publish_errors(p):
        raise AppError("cannot keep published: " + "; ".join(pm.publish_errors(p)))
    new = bs.put_json(P, _name(pid), p, etag=request.headers.get("If-Match") or current)
    audit.log_event("product_updated", pid, g.user["uid"])
    return jsonify(_out(p, new))


def _set_status(pid, status):
    p, etag = bs.get_json(P, _name(pid))
    _own(p)
    if status == "Published":
        errs = pm.publish_errors(p)
        if errs:
            raise AppError("cannot publish: " + "; ".join(errs))
    p["publication_status"], p["updated_at"] = status, pm.now()
    new = bs.put_json(P, _name(pid), p, etag=etag)
    audit.log_event(f"product_{status.lower()}", pid, g.user["uid"])
    return jsonify(_out(p, new))


@bp.post("/api/seller/products/<pid>/publish")
@auth.require("seller", "admin")
def seller_publish(pid):
    return _set_status(pid, "Published")


@bp.post("/api/seller/products/<pid>/unpublish")
@auth.require("seller", "admin")
def seller_unpublish(pid):
    return _set_status(pid, "Unpublished")


@bp.post("/api/seller/products/<pid>/image")
@auth.require("seller", "admin")
def seller_image(pid):
    p, etag = bs.get_json(P, _name(pid))
    _own(p)
    if not request.files.get("image"):
        raise AppError("image file is required (form field 'image')")
    _store_image(p, request.files["image"])
    p["updated_at"] = pm.now()
    return jsonify(_out(p, bs.put_json(P, _name(pid), p, etag=etag)))


@bp.delete("/api/seller/products/<pid>")
@auth.require("seller", "admin")
def seller_delete(pid):
    p, etag = bs.get_json(P, _name(pid))
    _own(p)
    bs.delete(P, _name(pid), etag=request.headers.get("If-Match") or etag)
    if p.get("image_blob_name"):
        try:
            bs.delete(IMG, p["image_blob_name"])
        except Exception:  # noqa
            pass
    audit.log_event("product_deleted", pid, g.user["uid"])
    return jsonify({"deleted": pid})
