"""Audit events: one JSON blob per event (unique name, no append conflicts). Never log secrets."""
import logging
import socket
import uuid
from datetime import datetime, timezone

import config
from services import blob_service as bs

log = logging.getLogger(__name__)


def log_event(event_type, entity_id="", actor_id="system", result="success", details=None):
    ts = datetime.now(timezone.utc)
    eid = uuid.uuid4().hex
    name = f"{ts:%Y/%m/%d}/{ts:%H%M%S%f}-{eid[:8]}-{event_type}.json"
    rec = {"event_id": eid, "event_type": event_type, "entity_id": entity_id, "actor_id": actor_id,
           "timestamp": ts.isoformat(), "result": result, "instance": socket.gethostname(), "details": details or {}}
    try:
        bs.put_json(config.CONTAINERS["audit"], name, rec)
    except Exception as e:  # auditing must never break the business operation
        log.warning("audit write failed (%s): %s", event_type, e)
