"""Azure Queue Storage via Managed Identity (Storage Queue Data Contributor)."""
import json
import logging

from azure.core.exceptions import ResourceExistsError
from azure.storage.queue import QueueServiceClient

import config
from services.identity_service import get_credential

log = logging.getLogger(__name__)
_c = None


def client():
    global _c
    if _c is None:
        _c = QueueServiceClient(account_url=config.QUEUE_ENDPOINT, credential=get_credential())
    return _c


def _q(name):
    return client().get_queue_client(name)


def ensure():
    for n in (config.ORDER_QUEUE, config.POISON_QUEUE):
        try:
            _q(n).create_queue()
        except ResourceExistsError:
            pass


def send(name, obj):
    _q(name).send_message(json.dumps(obj))


def receive(name, max_messages=10, visibility=30):
    return list(_q(name).receive_messages(max_messages=max_messages, visibility_timeout=visibility))


def delete(name, msg):
    _q(name).delete_message(msg)


def peek(name, n=20):
    return [{"id": m.id, "dequeue_count": m.dequeue_count, "inserted_on": str(m.inserted_on), "content": json.loads(m.content)}
            for m in _q(name).peek_messages(max_messages=n)]


def count(name):
    return _q(name).get_queue_properties().approximate_message_count
