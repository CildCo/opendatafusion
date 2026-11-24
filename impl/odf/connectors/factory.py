from odf.connectors.clickhouse import ClickHouseSource
from odf.connectors.es import ESSink, ESSource
from odf.connectors.file import FileSource
from odf.connectors.http import HTTPSink, HTTPSource
from odf.connectors.kafka import KafkaSink, KafkaSource
from odf.connectors.s3 import S3Source
from odf.connectors.hive import HiveSource
from odf.connectors.dm import DmSource
from odf.connectors.sql import SQLSink, SQLSource
from odf.connectors.trino import TrinoSource

SOURCE_SQL_KINDS = ("postgres", "postgresql", "sqlite", "mysql",
                    "mariadb", "oracle", "mssql", "sqlserver")
SINK_KINDS = ("postgres", "postgresql", "sqlite", "mysql", "mariadb")


def source_for(ds, dag):
    from odf.connectors.registry import EXTRA_SOURCES
    if ds.kind in EXTRA_SOURCES:
        return EXTRA_SOURCES[ds.kind](ds, dag)
    if ds.kind == "file":
        return FileSource(ds, dag)
    if ds.kind == "clickhouse":
        return ClickHouseSource(ds, dag)
    if ds.kind == "trino":
        return TrinoSource(ds, dag)
    if ds.kind in SOURCE_SQL_KINDS:
        return SQLSource(ds, dag)
    if ds.kind == "http":
        return HTTPSource(ds, dag)
    if ds.kind == "es":
        return ESSource(ds, dag)
    if ds.kind == "kafka":
        return KafkaSource(ds, dag)
    if ds.kind == "s3":
        return S3Source(ds, dag)
    if ds.kind == "hive":
        return HiveSource(ds, dag)
    if ds.kind == "dm":
        return DmSource(ds, dag)
    if ds.kind == "airbyte":
        from odf.connectors.airbyte import AirbyteSource
        return AirbyteSource(ds, dag)
    raise ValueError("unsupported source kind: %s" % ds.kind)


def sink_for(ds, dag):
    from odf.connectors.registry import EXTRA_SINKS
    if ds.kind in EXTRA_SINKS:
        return EXTRA_SINKS[ds.kind](ds, dag)
    if ds.kind in SINK_KINDS:
        return SQLSink(ds, dag)
    if ds.kind == "http":
        return HTTPSink(ds, dag)
    if ds.kind == "es":
        return ESSink(ds, dag)
    if ds.kind == "kafka":
        return KafkaSink(ds, dag)
    raise ValueError("unsupported sink kind: %s" % ds.kind)
