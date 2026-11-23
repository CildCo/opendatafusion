from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlparse


def _client(dsn, timeout=5):
    from pymongo import MongoClient
    return MongoClient(dsn, serverSelectionTimeoutMS=max(1, timeout) * 1000)


def database_name(dsn):
    parsed = urlparse(dsn or "")
    name = (parsed.path or "").lstrip("/").split("/")[0]
    if not name:
        raise ValueError("mongodb datasource needs a database in the dsn")
    return name


def _type(value):
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "bigint"
    if isinstance(value, float):
        return "double"
    if isinstance(value, Decimal):
        return "decimal"
    if isinstance(value, datetime):
        return "timestamp"
    if isinstance(value, date):
        return "date"
    if isinstance(value, bytes):
        return "binary"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    if value is None:
        return "null"
    return "text"


def ping(dsn, timeout=5):
    client = _client(dsn, timeout)
    try:
        client.admin.command("ping")
        return True
    finally:
        client.close()


def collections(dsn, timeout=5):
    client = _client(dsn, timeout)
    try:
        database = database_name(dsn)
        db = client[database]
        out = []
        for name in sorted(db.list_collection_names()):
            if name.startswith("system."):
                continue
            doc = db[name].find_one()
            columns = [{"name": key, "type": _type(value)}
                       for key, value in (doc or {}).items()]
            out.append({"schema": database, "table": name,
                        "columns": columns})
        return out
    finally:
        client.close()
