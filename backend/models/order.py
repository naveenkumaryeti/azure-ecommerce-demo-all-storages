from models.product import now


def build(oid, customer, product, qty, address):
    """Order JSON (archive in orders/{order_id}.json). All money values come from the stored product, never the browser."""
    ts = now()
    return {"order_id": oid, "customer_id": customer["uid"], "customer_name": customer.get("name", ""),
            "product_id": product["product_id"], "product_name": product["product_name"], "colour": product.get("colour", ""),
            "image_blob_name": product.get("image_blob_name", ""), "seller_id": product["seller_id"], "quantity": qty,
            "unit_price": product["price"], "total_amount": round(product["price"] * qty, 2), "delivery_address": address,
            "payment_method": "COD", "payment_status": "Pending", "order_status": "Confirmed", "delivery_status": "Pending",
            "inventory_applied": False, "outbox_pending": True, "delivered_at": "", "created_at": ts, "updated_at": ts,
            "history": [{"status": "Confirmed", "at": ts, "by": customer["uid"]}]}
