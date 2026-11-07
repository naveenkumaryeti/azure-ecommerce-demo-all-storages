"""All Azure Blob Storage access. One individual JSON blob per entity, ETag-protected updates."""
import json
import logging
from datetime import datetime, timezone

from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient, ContentSettings

import config
from services.identity_service import get_credential

log = logging.getLogger(__name__)
_client = None
state = {"last_success_op": None, "last_success_at": None, "last_status": "no operations yet"}


def client():
    global _client
    if _client is None:
        _client = BlobServiceClient(account_url=config.BLOB_ENDPOINT, credential=get_credential())
    return _client


def _ok(op):
    state.update(last_success_op=op, last_success_at=datetime.now(timezone.utc).isoformat(), last_status="success")


def ensure_containers():
    for c in config.CONTAINERS.values():
        try:
            client().create_container(c)
        except ResourceExistsError:
            pass


def put_json(container, name, obj, etag=None, create_only=False):
    """Upload JSON. etag -> only overwrite if unchanged (412 otherwise). create_only -> fail if exists."""
    kw = {"overwrite": not create_only,
          "content_settings": ContentSettings(content_type="application/json")}
    if etag:
        kw.update(etag=etag, match_condition=MatchConditions.IfNotModified)
    res = client().get_blob_client(container, name).upload_blob(json.dumps(obj, indent=2).encode(), **kw)
    _ok(f"upload {container}/{name}")
    return res["etag"]


def get_json(container, name):
    dl = client().get_blob_client(container, name).download_blob()
    data = json.loads(dl.readall())
    _ok(f"read {container}/{name}")
    return data, dl.properties.etag


def list_json(container):
    out = []
    for b in client().get_container_client(container).list_blobs():
        if b.name.endswith(".json"):
            out.append(get_json(container, b.name))
    return out


def delete(container, name, etag=None):
    kw = {"etag": etag, "match_condition": MatchConditions.IfNotModified} if etag else {}
    client().get_blob_client(container, name).delete_blob(**kw)
    _ok(f"delete {container}/{name}")


def upload_blob(container, name, data, content_type):
    client().get_blob_client(container, name).upload_blob(
        data, overwrite=True, content_settings=ContentSettings(content_type=content_type))
    _ok(f"upload {container}/{name}")


def download(container, name):
    dl = client().get_blob_client(container, name).download_blob()
    return dl.readall(), dl.properties.content_settings.content_type or "application/octet-stream"


def list_containers():
    return [c.name for c in client().list_containers()]


def list_blobs(container):
    return [{"name": b.name, "size": b.size, "content_type": b.content_settings.content_type,
             "last_modified": b.last_modified.isoformat(), "etag": b.etag}
            for b in client().get_container_client(container).list_blobs()]


def stats():
    counts, newest = {}, None
    for key in ("products", "images", "orders", "audit"):
        n = 0
        for b in client().get_container_client(config.CONTAINERS[key]).list_blobs():
            n += 1
            if key != "audit" and (newest is None or b.last_modified > newest):
                newest = b.last_modified
        counts[key] = n
    _ok("stats")
    return counts, newest.isoformat() if newest else None
