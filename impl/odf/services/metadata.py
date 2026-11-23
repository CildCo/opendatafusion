import json
import re
from urllib.parse import quote

from sqlalchemy import create_engine, inspect

from odf.models import Column, Dataset, Datasource
from odf.connectors.registry import supports
from odf.services.datasource import connect_args_for, get_dsn
from odf.trino.client import client_for_datasource

_CATALOG = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def normalize_table(schema: str, table: str) -> str:
    return "%s.%s" % (schema, table)


def list_tables(session, datasource_id: int) -> list[dict]:
    out = []
    for d in session.query(Dataset).filter_by(datasource_id=datasource_id).all():
        cols = session.query(Column).filter_by(dataset_id=d.id).all()
        out.append({"schema": d.schema_name, "table": d.table_name,
                    "columns": [{"name": c.name, "type": c.data_type}
                                for c in cols]})
    return out


def _existing_columns(session, datasource_id: int) -> dict:
    out = {}
    for d in session.query(Dataset).filter_by(
            datasource_id=datasource_id).all():
        out[(d.schema_name, d.table_name)] = {
            c.name: c.data_type
            for c in session.query(Column).filter_by(dataset_id=d.id).all()}
    return out


def _dependents(session, dataset_id: int) -> bool:
    from odf.models import DatasetTag, QualityRule, StandardMapping
    for model in (QualityRule, DatasetTag, StandardMapping):
        if session.query(model).filter_by(dataset_id=dataset_id).first():
            return True
    return False


def _upsert(session, ds, tables: dict) -> None:
    """Create or update dataset rows in place.

    Deleting and recreating them would break every quality rule, tag and
    standard mapping that points at a dataset, so rows are matched by schema
    and table name and their columns are diffed.
    """
    existing = {(d.schema_name, d.table_name): d
                for d in session.query(Dataset)
                .filter_by(datasource_id=ds.id).all()}
    for (schema, table), columns in tables.items():
        d = existing.get((schema, table))
        if d is None:
            d = Dataset(datasource_id=ds.id, schema_name=schema,
                        table_name=table)
            session.add(d)
            session.flush()
        current = {c.name: c for c in
                   session.query(Column).filter_by(dataset_id=d.id).all()}
        wanted = {c["name"]: c["type"] for c in columns}
        for name, kind in wanted.items():
            if name in current:
                current[name].data_type = kind
            else:
                session.add(Column(dataset_id=d.id, name=name,
                                   data_type=kind))
        for name, column in current.items():
            if name not in wanted:
                session.delete(column)
    for key, d in existing.items():
        if key in tables or _dependents(session, d.id):
            continue
        session.query(Column).filter_by(dataset_id=d.id).delete()
        session.delete(d)
    session.commit()


def _detect_drift(session, ds, before: dict, after: dict):
    from odf.services.alerts import raise_alert
    for (schema, table), new in after.items():
        old = before.get((schema, table))
        if old is None:
            continue
        added = sorted(set(new) - set(old))
        removed = sorted(set(old) - set(new))
        changed = sorted(k for k in set(old) & set(new)
                         if old[k] != new[k])
        if not (added or removed or changed):
            continue
        raise_alert(
            session, ds.project_id, "warning",
            "schema drift: %s.%s" % (schema, table),
            {"datasource_id": ds.id, "table": "%s.%s" % (schema, table),
             "added": added, "removed": removed,
             "type_changed": [{"column": k, "from": old[k], "to": new[k]}
                              for k in changed]})


def _sync_file(session, ds) -> int:
    from odf import filesource
    path = filesource.path_for(ds)
    name = filesource.table_name_for(path)
    columns = filesource.describe(path)
    before = _existing_columns(session, ds.id)
    tables = {(filesource.SCHEMA, name): columns}
    _upsert(session, ds, tables)
    _detect_drift(session, ds, before,
                  {k: {c["name"]: c["type"] for c in v}
                   for k, v in tables.items()})
    return 1


def _sync_clickhouse(session, ds) -> int:
    from odf import clickhouse
    found = clickhouse.tables(ds)
    before = _existing_columns(session, ds.id)
    tables = {(t["schema"], t["table"]): t["columns"] for t in found}
    _upsert(session, ds, tables)
    _detect_drift(session, ds, before,
                  {k: {c["name"]: c["type"] for c in v}
                   for k, v in tables.items()})
    return len(found)


def _sync_sql(session, ds) -> int:
    dsn = get_dsn(ds)
    args = connect_args_for(ds.kind, dsn)
    engine = create_engine(dsn, connect_args=args)
    insp = inspect(engine)
    before = _existing_columns(session, ds.id)

    if engine.dialect.name == "sqlite":
        schemas = ["main"]
    elif engine.dialect.name in ("oracle", "mssql"):
        schemas = [insp.default_schema_name]
    else:
        schemas = [s for s in insp.get_schema_names()
                   if s not in ("pg_catalog", "information_schema")]

    tables = {}
    for schema in schemas:
        for table in insp.get_table_names(schema=schema):
            tables[(schema, table)] = [
                {"name": c["name"], "type": str(c["type"])}
                for c in insp.get_columns(table, schema=schema)]
    _upsert(session, ds, tables)
    _detect_drift(session, ds, before,
                  {k: {c["name"]: c["type"] for c in v}
                   for k, v in tables.items()})
    return len(tables)


def _sync_es(session, ds) -> int:
    from odf.services.net import request as outbound
    from odf.settings import get_settings
    settings = get_settings()
    allowed = tuple(item.strip() for item in
                    (settings.http_allowed_hosts or "").split(",")
                    if item.strip())
    base = get_dsn(ds).rstrip("/")

    def call(path):
        code, _, payload = outbound(
            base + path, timeout=10,
            allow_private=settings.http_allow_private,
            allowed_hosts=allowed, max_bytes=5 * 1024 * 1024)
        if code >= 400:
            raise ValueError("elasticsearch answered HTTP %d" % code)
        return json.loads(payload.decode("utf-8", "replace"))

    indices = [row.get("index") for row in call(
        "/_cat/indices?format=json&h=index") if row.get("index")]
    tables = {}
    for index in indices:
        if index.startswith("."):
            continue
        mapping = call("/%s/_mapping" % quote(index, safe=""))
        body = next(iter(mapping.values()), {})
        props = (body.get("mappings") or {}).get("properties") or {}
        tables[("es", index)] = [
            {"name": name, "type": (spec or {}).get("type", "object")}
            for name, spec in props.items()]
    before = _existing_columns(session, ds.id)
    _upsert(session, ds, tables)
    _detect_drift(session, ds, before,
                  {k: {c["name"]: c["type"] for c in v}
                   for k, v in tables.items()})
    return len(tables)


def _sync_trino(session, ds) -> int:
    client = client_for_datasource(ds)
    catalog = getattr(client, "catalog", "") or ""
    if not _CATALOG.match(catalog):
        raise ValueError("trino datasource needs a catalog in the dsn")
    result = client.query(
        "select table_schema, table_name, column_name, data_type "
        "from %s.information_schema.columns "
        "where table_schema not in ('information_schema') "
        "order by table_schema, table_name, ordinal_position" % catalog,
        max_rows=200000)
    grouped = {}
    for row in result["rows"]:
        grouped.setdefault(
            (row["table_schema"], row["table_name"]), []).append(
            {"name": row["column_name"], "type": row["data_type"]})
    before = _existing_columns(session, ds.id)
    _upsert(session, ds, grouped)
    _detect_drift(session, ds, before,
                  {k: {c["name"]: c["type"] for c in v}
                   for k, v in grouped.items()})
    return len(grouped)


def sync_datasource(session, datasource_id: int) -> int:
    ds = session.get(Datasource, datasource_id)
    if not ds:
        raise ValueError("datasource not found")
    if not supports(ds.kind, "metadata"):
        raise ValueError(
            "%s is a pipeline connector; its schema cannot be synchronised"
            % ds.kind)
    if ds.kind == "es":
        return _sync_es(session, ds)
    if ds.kind == "file":
        return _sync_file(session, ds)
    if ds.kind == "clickhouse":
        return _sync_clickhouse(session, ds)
    if ds.kind == "trino":
        return _sync_trino(session, ds)
    return _sync_sql(session, ds)
