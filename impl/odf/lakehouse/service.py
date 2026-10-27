import re

from odf.trino.client import client_for_datasource, literal

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")


def project_schema(project_id: int) -> str:
    return "odf_p%d" % int(project_id)


def _catalog(client) -> str:
    catalog = getattr(client, "catalog", "") or ""
    if not _IDENT.match(catalog):
        raise ValueError("trino datasource needs a catalog in the dsn")
    return catalog


def ensure_schema(client, project_id: int) -> str:
    schema = project_schema(project_id)
    client.execute('CREATE SCHEMA IF NOT EXISTS "%s"."%s"'
                   % (_catalog(client), schema))
    return schema


def _column_rows(client, where: str) -> list:
    sql = ("select table_name, column_name, data_type "
           "from %s.information_schema.columns where %s "
           "order by table_name, ordinal_position"
           % (_catalog(client), where))
    return client.query(sql, max_rows=200000)["rows"]


def list_tables(client, schema: str) -> list:
    grouped = {}
    for row in _column_rows(client, "table_schema = %s" % literal(schema)):
        grouped.setdefault(row["table_name"], []).append(
            {"name": row["column_name"], "type": row["data_type"]})
    return [{"table": name, "columns": columns}
            for name, columns in grouped.items()]


def table_columns(client, schema: str, table: str) -> list:
    where = ("table_schema = %s and table_name = %s"
             % (literal(schema), literal(table)))
    return [{"name": row["column_name"], "type": row["data_type"]}
            for row in _column_rows(client, where)]
