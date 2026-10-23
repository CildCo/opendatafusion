from sqlalchemy import create_engine, inspect

from odf.models import Column, Dataset
from odf.services.datasource import connect_args_for, get_dsn


def _split(table):
    if "." in table:
        return table.split(".", 1)
    return None, table


def table_column_info(session, datasource, table):
    if not isinstance(table, str) or not table:
        raise ValueError("table is required")
    schema, name = _split(table)
    q = session.query(Dataset).filter_by(datasource_id=datasource.id,
                                         table_name=name)
    if schema:
        q = q.filter_by(schema_name=schema)
    d = q.first()
    if d:
        return [{"name": c.name, "type": c.data_type}
                for c in session.query(Column).filter_by(dataset_id=d.id)
                .order_by(Column.id).all()]
    if datasource.kind == "file":
        from odf import filesource
        path = filesource.path_for(datasource)
        if schema not in (None, filesource.SCHEMA) or \
                name != filesource.table_name_for(path):
            raise ValueError("table not found: %s" % table)
        return filesource.describe(path)
    if datasource.kind == "clickhouse":
        from odf import clickhouse
        return clickhouse.columns(datasource, table)
    dsn = get_dsn(datasource)
    args = connect_args_for(datasource.kind, dsn)
    engine = create_engine(dsn, connect_args=args)
    try:
        insp = inspect(engine)
        try:
            cols = insp.get_columns(name, schema=schema) if schema \
                else insp.get_columns(name)
        except Exception:
            raise ValueError("table not found: %s" % table)
    finally:
        engine.dispose()
    if not cols:
        raise ValueError("table not found: %s" % table)
    return [{"name": c["name"], "type": str(c["type"])} for c in cols]


def table_columns(session, datasource, table):
    return [c["name"] for c in table_column_info(session, datasource, table)]
