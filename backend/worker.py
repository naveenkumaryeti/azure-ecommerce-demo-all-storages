"""Background consumer process (systemd: quickkart-worker). Disabled by default so the demo can run the consumer manually."""
import logging
import time

from app import ensure_ready
from services import order_service, queue_worker

logging.basicConfig(level=logging.INFO)
last = 0
while True:
    try:
        ensure_ready()
        queue_worker.process_batch()
        if time.time() - last > 60:
            order_service.reconcile()
            last = time.time()
    except Exception as e:  # noqa
        logging.warning("worker loop error: %s", e)
    time.sleep(5)
