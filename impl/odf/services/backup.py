import base64
import json
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, LargeBinary

from odf.db import Base

EXCLUDED = {"audit_log", "datasource_health"}
FORMAT = "odf-backup"
VERSION = 1


def _dump(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": base64.b64encode(value).decode()}
    return value


def _load(value, column):
    if isinstance(value, dict) and "__bytes__" in value:
        return base64.b64decode(value["__bytes__"])
    if isinstance(value, str) and isinstance(column.type, DateTime):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    if isinstance(value, str) and isinstance(column.type, Date):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return value
    return value


def _tables():
    return [t for t in Base.metadata.sorted_tables
            if t.name not in EXCLUDED]


def export_bytes(session):
    tables = {}
    for table in _tables():
        rows = session.execute(table.select()).mappings().all()
        tables[table.name] = [
            {key: _dump(value) for key, value in row.items()} for row in rows]
    payload = {"format": FORMAT, "version": VERSION,
               "created_at": datetime.utcnow().isoformat() + "Z",
               "tables": tables}
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def restore(session, raw, actor=""):
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    data = json.loads(raw)
    if data.get("format") != FORMAT or data.get("version") != VERSION:
        raise ValueError("unsupported backup format")
    tables = _tables()
    known = {t.name: t for t in tables}
    payload = data.get("tables") or {}
    unknown = set(payload) - set(known)
    if unknown:
        raise ValueError("unknown tables: %s" % ", ".join(sorted(unknown)))
    for table in reversed(tables):
        session.execute(table.delete())
    for table in tables:
        rows = payload.get(table.name) or []
        if not rows:
            continue
        cleaned = []
        for row in rows:
            item = {}
            for key, value in row.items():
                if key not in table.c:
                    continue
                item[key] = _load(value, table.c[key])
            cleaned.append(item)
        if cleaned:
            session.execute(table.insert(), cleaned)
    session.commit()
    return {name: len(payload.get(name) or []) for name in payload}
