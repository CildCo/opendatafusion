from sqlalchemy import create_engine, inspect

from odf.models import Column, Dataset, Datasource
from odf.services.datasource import connect_args_for, get_dsn


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


def _clear(session, datasource_id: int):
    for d in session.query(Dataset).filter_by(
            datasource_id=datasource_id).all():
        session.query(Column).filter_by(dataset_id=d.id).delete()
        session.delete(d)


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
    _clear(session, ds.id)
    session.flush()
    d = Dataset(datasource_id=ds.id, schema_name=filesource.SCHEMA,
                table_name=name)
    session.add(d)
    session.flush()
    for col in columns:
        session.add(Column(dataset_id=d.id, name=col["name"],
                           data_type=col["type"]))
    session.commit()
    after = {(filesource.SCHEMA, name):
             {c["name"]: c["type"] for c in columns}}
    _detect_drift(session, ds, before, after)
    return 1


def _sync_clickhouse(session, ds) -> int:
    from odf import clickhouse
    tables = clickhouse.tables(ds)
    before = _existing_columns(session, ds.id)
    _clear(session, ds.id)
    session.flush()
    after = {}
    for table in tables:
        d = Dataset(datasource_id=ds.id, schema_name=table["schema"],
                    table_name=table["table"])
        session.add(d)
        session.flush()
        after[(table["schema"], table["table"])] = {
            c["name"]: c["type"] for c in table["columns"]}
        for col in table["columns"]:
            session.add(Column(dataset_id=d.id, name=col["name"],
                               data_type=col["type"]))
    session.commit()
    _detect_drift(session, ds, before, after)
    return len(tables)


def _sync_sql(session, ds) -> int:
    dsn = get_dsn(ds)
    args = connect_args_for(ds.kind, dsn)
    engine = create_engine(dsn, connect_args=args)
    insp = inspect(engine)
    before = _existing_columns(session, ds.id)
    _clear(session, ds.id)
    session.flush()

    if engine.dialect.name == "sqlite":
        schemas = ["main"]
    elif engine.dialect.name in ("oracle", "mssql"):
        schemas = [insp.default_schema_name]
    else:
        schemas = [s for s in insp.get_schema_names()
                   if s not in ("pg_catalog", "information_schema")]

    count = 0
    after = {}
    for schema in schemas:
        for table in insp.get_table_names(schema=schema):
            d = Dataset(datasource_id=ds.id, schema_name=schema, table_name=table)
            session.add(d)
            session.flush()
            columns = insp.get_columns(table, schema=schema)
            after[(schema, table)] = {c["name"]: str(c["type"])
                                      for c in columns}
            for col in columns:
                session.add(Column(dataset_id=d.id, name=col["name"],
                                   data_type=str(col["type"])))
            count += 1
    session.commit()
    _detect_drift(session, ds, before, after)
    return count


def sync_datasource(session, datasource_id: int) -> int:
    ds = session.get(Datasource, datasource_id)
    if not ds:
        raise ValueError("datasource not found")
    if ds.kind == "file":
        return _sync_file(session, ds)
    if ds.kind == "clickhouse":
        return _sync_clickhouse(session, ds)
    return _sync_sql(session, ds)
