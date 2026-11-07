import uuid
from datetime import datetime, timezone

STATUSES = ("Draft", "Published", "Out of Stock", "Unpublished")


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(data, seller_id, existing=None):
    """Validate seller input -> product JSON stored as products/{product_id}.json. Price may stay empty while Draft."""
    name = str(data.get("product_name", "")).strip()
    if not name:
        raise ValueError("product_name is required")
    try:
        qty = int(data.get("available_quantity"))
    except (TypeError, ValueError):
        raise ValueError("available_quantity must be a whole number")
    if qty < 0:
        raise ValueError("available_quantity must be >= 0")
    raw = data.get("price")
    price = None
    if raw not in (None, ""):
        try:
            price = round(float(raw), 2)
        except (TypeError, ValueError):
            raise ValueError("price must be a number")
        if price <= 0:
            raise ValueError("price must be greater than 0")
    p = dict(existing or {})
    pid = p.get("product_id") or "PROD-" + uuid.uuid4().hex[:8].upper()
    p.update(product_id=pid, product_name=name, colour=str(data.get("colour", "")).strip(),
             product_status=str(data.get("product_status", "")).strip(), category=str(data.get("category") or "General").strip(),
             description=str(data.get("description", "")).strip()[:1000], available_quantity=qty, price=price,
             seller_id=p.get("seller_id") or seller_id, image_blob_name=p.get("image_blob_name", ""),
             publication_status=p.get("publication_status", "Draft"))
    if qty == 0 and p["publication_status"] == "Published":
        p["publication_status"] = "Out of Stock"
    elif qty > 0 and p["publication_status"] == "Out of Stock":
        p["publication_status"] = "Published"
    p.setdefault("created_at", now())
    p["updated_at"] = now()
    return p


def publish_errors(p):
    e = []
    if not p.get("price") or p["price"] <= 0:
        e.append("a valid selling price is required")
    if p["available_quantity"] < 1:
        e.append("stock must be at least 1")
    if not p.get("image_blob_name"):
        e.append("upload a product image first")
    return e


def public(p):
    return {k: v for k, v in p.items() if k != "reserved_orders"}
