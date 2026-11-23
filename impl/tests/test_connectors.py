import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from types import SimpleNamespace

import pytest
from sqlalchemy import Column, Integer, MetaData, String, Table

from odf.connectors.es import ESSink, ESSource
from odf.connectors.http import HTTPSink, HTTPSource
from odf.connectors.sql import _coerce
from odf.models import Datasource
from odf.services.crypto import encrypt_secret


@pytest.fixture(autouse=True)
def _http_settings(monkeypatch):
    settings = SimpleNamespace(http_allow_private=True,
                               http_allowed_hosts="",
                               http_timeout_s=5,
                               http_max_response_mb=5)
    monkeypatch.setattr("odf.connectors.http.get_settings",
                        lambda: settings)
    monkeypatch.setattr("odf.connectors.es.get_settings",
                        lambda: settings)


def test_coerce_cursor_types():
    t = Table("t", MetaData(), Column("id", Integer), Column("v", String))
    assert _coerce(t.c.id, "3") == 3
    assert _coerce(t.c.v, "3") == "3"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"data": [{"id": 1, "ts": "t1"},
                                    {"id": 2, "ts": "t2"}]}).encode()
        self._send(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.server.payloads.append(self.rfile.read(length))
        if self.path.endswith("/_search"):
            body = json.dumps({"hits": {"hits": [
                {"_source": {"id": 1}}, {"_source": {"id": 2}}]}}).encode()
        else:
            body = json.dumps({"errors": False}).encode()
        self._send(body)

    def _send(self, body):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture()
def server():
    srv = HTTPServer(("127.0.0.1", 0), Handler)
    srv.payloads = []
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield "http://127.0.0.1:%d" % srv.server_address[1], srv
    srv.shutdown()


def test_http_source(server):
    base, _ = server
    src = HTTPSource(None, {"source_url": base + "/data",
                            "records_path": "data",
                            "cursor_column": "ts", "pk": "id"})
    rows, cursor = src.read(None, 10)
    assert len(rows) == 2 and cursor == "t2"


def test_http_source_blocks_private_by_default(server, monkeypatch):
    base, _ = server
    monkeypatch.setattr(
        "odf.connectors.http.get_settings",
        lambda: SimpleNamespace(http_allow_private=False,
                                http_allowed_hosts="",
                                http_timeout_s=5,
                                http_max_response_mb=5))
    src = HTTPSource(None, {"source_url": base + "/data",
                            "records_path": "data"})
    with pytest.raises(ValueError):
        src.read(None, 10)


def test_http_sink(server):
    base, srv = server
    sink = HTTPSink(None, {"sink_url": base + "/sink"})
    assert sink.write([{"id": 1}, {"id": 2}]) == 2
    assert len(srv.payloads) == 2


def test_es_source_and_sink(server):
    base, srv = server
    ds = Datasource(kind="es", dsn_encrypted=encrypt_secret(base))
    src = ESSource(ds, {"source_table": "idx"})
    rows, _ = src.read(None, 10)
    assert len(rows) == 2
    sink = ESSink(ds, {"sink_table": "idx", "pk": "id"})
    assert sink.write([{"id": 1}, {"id": 2}]) == 2


def test_kafka_source_and_sink(monkeypatch):
    import kafka

    class Record:
        def __init__(self, partition, offset, value):
            self.partition = partition
            self.offset = offset
            self.value = value

    class Consumer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def subscribe(self, topics):
            self.topics = topics

        def assign(self, partitions):
            self.assigned = partitions

        def seek(self, partition, offset):
            pass

        def poll(self, timeout_ms=0, max_records=0):
            key = kafka.TopicPartition("events", 0)
            return {key: [Record(0, 5, b'{"id": 1}'),
                          Record(0, 6, b'{"id": 2}')]}

        def close(self):
            pass

    class Producer:
        def __init__(self, **kwargs):
            self.sent = []

        def send(self, topic, row):
            self.sent.append((topic, row))

        def flush(self, timeout=None):
            pass

        def close(self):
            pass

    monkeypatch.setattr(kafka, "KafkaConsumer", Consumer)
    monkeypatch.setattr(kafka, "KafkaProducer", Producer)
    from odf.connectors.kafka import KafkaSink, KafkaSource
    ds = Datasource(kind="kafka", dsn_encrypted=encrypt_secret(
        "kafka://kafka:9092"))
    source = KafkaSource(ds, {"source_table": "events",
                              "consumer_group": "odf-test"})
    rows, cursor = source.read(None, 10)
    assert [row["id"] for row in rows] == [1, 2]
    assert cursor == '{"0": 7}'
    rows, cursor = source.read(cursor, 10)
    assert rows and cursor == '{"0": 7}'
    sink = KafkaSink(ds, {"sink_table": "events"})
    assert sink.write([{"id": 1}, {"id": 2}]) == 2


def test_s3_source_delegates_to_the_file_reader(monkeypatch, tmp_path):
    path = tmp_path / "orders.csv"
    path.write_text("id,name\n1,a\n2,b\n", encoding="utf-8")
    calls = []
    monkeypatch.setattr("odf.connectors.s3.temp_files",
                        lambda dsn: (calls.append(dsn) or ([path], str(tmp_path))))
    monkeypatch.setattr("odf.filesource._allowed_roots",
                        lambda: [tmp_path.resolve()])
    from odf.connectors.s3 import S3Source
    ds = Datasource(kind="s3", dsn_encrypted=encrypt_secret("s3://b/k"))
    source = S3Source(ds, {"source_table": "orders", "pk": "id"})
    rows, _ = source.read(None, 10)
    assert [row["id"] for row in rows] == [1, 2]
    assert calls


def test_hive_query_and_tables(monkeypatch):
    import pyhive.hive as pyhive_hive

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, sql):
            self.sql = sql
            if sql == "SHOW TABLES":
                self.rows = [("default", "events", False)]
                self.description = None
            elif sql.startswith("DESCRIBE"):
                self.rows = [("id", "bigint", None), ("name", "string", None),
                             ("# Partition Information", None, None)]
                self.description = None
            else:
                self.rows = [(1, "a")]
                self.description = [("id",), ("name",)]

        def fetchall(self):
            return self.rows

        def fetchmany(self, n):
            return self.rows[:n]

        def close(self):
            pass

    class Conn:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(pyhive_hive, "Connection", Conn)
    from odf.connectors import hive
    dsn = "hive://odf:pw@hive:10000/default?auth=NOSASL"
    assert hive.ping(dsn) is True
    result = hive.query(dsn, "select id, name from events", 10)
    assert result["rows"] == [{"id": 1, "name": "a"}]
    tables = hive.tables(dsn)
    assert tables[0]["table"] == "events"
    assert [c["name"] for c in tables[0]["columns"]] == ["id", "name"]


def test_dm_query_and_tables(monkeypatch):
    import dmPython

    class Cursor:
        def __init__(self):
            self.rows = []

        def execute(self, sql):
            self.sql = sql
            if "ALL_TABLES" in sql:
                self.rows = [("APP", "ORDERS")]
                self.description = [("OWNER",), ("TABLE_NAME",)]
            elif "ALL_TAB_COLUMNS" in sql:
                self.rows = [("ID", "BIGINT"), ("TOTAL", "DECIMAL")]
                self.description = [("COLUMN_NAME",), ("DATA_TYPE",)]
            else:
                self.rows = [(1, 2.5)]
                self.description = [("ID",), ("TOTAL",)]

        def fetchall(self):
            return self.rows

        def fetchmany(self, n):
            return self.rows[:n]

        def close(self):
            pass

    class Conn:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def cursor(self):
            return Cursor()

        def close(self):
            pass

    monkeypatch.setattr(dmPython, "connect", lambda **kwargs: Conn(**kwargs))
    from odf.connectors import dm
    dsn = "dm://SYSDBA:pw@dm:5236/APP"
    assert dm.ping(dsn) is True
    result = dm.query(dsn, "select id, total from orders", 10)
    assert result["rows"] == [{"ID": 1, "TOTAL": 2.5}]
    tables = dm.tables(dsn)
    assert tables[0]["table"] == "ORDERS"
    assert [c["name"] for c in tables[0]["columns"]] == ["ID", "TOTAL"]
