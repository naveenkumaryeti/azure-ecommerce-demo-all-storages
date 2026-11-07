"""Configuration - environment variables only (no secrets in code). See docs/ENVIRONMENT.md."""
import logging
import os
import secrets

_acct = os.environ.get("STORAGE_ACCOUNT_NAME", "")
_sfx = os.environ.get("STORAGE_SUFFIX", "core.windows.net")
STORAGE_ACCOUNT_NAME = _acct
BLOB_ENDPOINT = os.environ.get("BLOB_ENDPOINT") or f"https://{_acct}.blob.{_sfx}"
QUEUE_ENDPOINT = os.environ.get("QUEUE_ENDPOINT") or f"https://{_acct}.queue.{_sfx}"
TABLE_ENDPOINT = os.environ.get("TABLE_ENDPOINT") or f"https://{_acct}.table.{_sfx}"
MANAGED_IDENTITY_CLIENT_ID = os.environ.get("AZURE_CLIENT_ID") or None  # only for user-assigned identity

CONTAINERS = {"products": "products", "images": "product-images", "orders": "orders", "audit": "audit-logs",
              "backups": "application-backups", "users": "users", "carts": "carts"}
HIDDEN_CONTAINERS = {"users"}  # never exposed in the explorer (contains password hashes)

ORDER_QUEUE = "quickkart-order-queue"
POISON_QUEUE = "quickkart-order-poison"
TABLE_QUEUE = "TableQueue"
TABLE_SERVICE = "TableService"
MAX_DEQUEUE = int(os.environ.get("QUEUE_MAX_DEQUEUE", "3"))          # attempts before poison queue
VISIBILITY_SECONDS = int(os.environ.get("QUEUE_VISIBILITY_SECONDS", "30"))

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
if not SESSION_SECRET:
    SESSION_SECRET = secrets.token_hex(32)
    logging.warning("SESSION_SECRET not set: using a random per-process key (tokens will not work across instances)")
TOKEN_MAX_AGE = 8 * 3600

SEEDS = [("seller", os.environ.get("SEED_SELLER_EMAIL", "seller@quickkart.demo"), os.environ.get("SEED_SELLER_PASSWORD", ""), "SELLER001", "Demo Seller"),
         ("admin", os.environ.get("SEED_ADMIN_EMAIL", "admin@quickkart.demo"), os.environ.get("SEED_ADMIN_PASSWORD", ""), "ADMIN001", "Delivery Admin"),
         ("customer", os.environ.get("SEED_CUSTOMER_EMAIL", "customer@quickkart.demo"), os.environ.get("SEED_CUSTOMER_PASSWORD", ""), "CUST001", "Demo Customer")]
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
