"""Azure Table Storage via Managed Identity (Storage Table Data Contributor): TableQueue + TableService."""
import logging

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableServiceClient, UpdateMode

import config
from services.identity_service import get_credential

log = logging.getLogger(__name__)
_c = None


def client():
    global _c
    if _c is None:
        _c = TableServiceClient(endpoint=config.TABLE_ENDPOINT, credential=get_credential())
    return _c


def _t(name):
    return client().get_table_client(name)


def ensure():
    for n in (config.TABLE_QUEUE, config.TABLE_SERVICE):
        client().create_table_if_not_exists(n)


def upsert(name, entity):
    _t(name).upsert_entity(entity, mode=UpdateMode.MERGE)


def get(name, pk, rk):
    try:
        return dict(_t(name).get_entity(pk, rk))
    except ResourceNotFoundError:
        return None


def list_all(name):
    return [dict(e) for e in _t(name).list_entities()]


def list_pk(name, pk):
    return [dict(e) for e in _t(name).query_entities("PartitionKey eq @pk", parameters={"pk": pk})]
