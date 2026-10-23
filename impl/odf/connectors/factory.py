from odf.connectors.clickhouse import ClickHouseSource
from odf.connectors.es import ESSink, ESSource
from odf.connectors.file import FileSource
from odf.connectors.http import HTTPSink, HTTPSource
from odf.connectors.sql import SQLSink, SQLSource

SOURCE_SQL_KINDS = ("postgres", "postgresql", "sqlite", "mysql",
                    "mariadb", "oracle", "mssql", "sqlserver")
SINK_KINDS = ("postgres", "postgresql", "sqlite", "mysql", "mariadb")


def source_for(ds, dag):
    if ds.kind == "file":
        return FileSource(ds, dag)
    if ds.kind == "clickhouse":
        return ClickHouseSource(ds, dag)
    if ds.kind in SOURCE_SQL_KINDS:
        return SQLSource(ds, dag)
    if ds.kind == "http":
        return HTTPSource(ds, dag)
    if ds.kind == "es":
        return ESSource(ds, dag)
    raise ValueError("unsupported source kind: %s" % ds.kind)


def sink_for(ds, dag):
    if ds.kind in SINK_KINDS:
        return SQLSink(ds, dag)
    if ds.kind == "http":
        return HTTPSink(ds, dag)
    if ds.kind == "es":
        return ESSink(ds, dag)
    raise ValueError("unsupported sink kind: %s" % ds.kind)
