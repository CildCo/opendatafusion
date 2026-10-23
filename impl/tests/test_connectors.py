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
    monkeypatch.setattr(
        "odf.connectors.http.get_settings",
        lambda: SimpleNamespace(http_allow_private=True,
                                http_allowed_hosts="",
                                http_timeout_s=5,
                                http_max_response_mb=5))


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
