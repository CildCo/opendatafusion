import json
import uuid

import httpx
import pytest

from odf.cdc import service as cdc
from odf.models import AuditLog, CdcSource


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _client(handler):
    return httpx.Client(base_url="http://debezium",
                        transport=httpx.MockTransport(handler))


def _config(**overrides):
    config = {"host": "cdc-postgres.stream.svc", "port": 5432,
              "database": "cdc", "user": "cdc",
              "schema_list": "public", "table_list": "public.events",
              "topic_prefix": "odf"}
    config.update(overrides)
    return config


def _recording(handler):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)

    return calls, wrapped


def test_connector_name_is_project_scoped_and_slugged():
    assert cdc.connector_name(7, "Orders CDC") == "odf-p7-orders-cdc"


def test_create_source_registers_connector_and_stores_password_encrypted(
        session, monkeypatch):
    def handler(request):
        if request.method == "PUT":
            return httpx.Response(201, json={"name": "odf-p1-x"})
        return httpx.Response(200, json={"connector": {"state": "RUNNING"},
                                         "tasks": []})

    calls, wrapped = _recording(handler)
    monkeypatch.setattr(cdc, "_client", lambda: _client(wrapped))
    slug = "cdc-%s" % uuid.uuid4().hex[:6]
    name = slug

    source = cdc.create_source(session, 1, name, _config(), "s3cret", "tester")

    put = [c for c in calls if c.method == "PUT"][0]
    body = json.loads(put.content)
    assert put.url.path == "/connectors/odf-p1-%s/config" % slug
    assert body["database.hostname"] == "cdc-postgres.stream.svc"
    assert body["database.password"] == "s3cret"
    assert body["table.include.list"] == "public.events"
    assert source.status == "running"
    assert source.password_encrypted != "s3cret"
    assert "s3cret" not in str(cdc.source_out(source))
    actions = [a.action for a in session.query(AuditLog)
               .filter_by(target=str(source.id)).all()]
    assert "create_cdc_source" in actions


def test_create_source_rejects_duplicate_name(session, monkeypatch):
    monkeypatch.setattr(cdc, "_client", lambda: _client(
        lambda r: httpx.Response(201, json={})
        if r.method == "PUT" else httpx.Response(200, json={"connector": {},
                                                           "tasks": []})))
    name = "dup-%s" % uuid.uuid4().hex[:6]
    cdc.create_source(session, 1, name, _config(), "x", "tester")
    with pytest.raises(ValueError, match="already exists"):
        cdc.create_source(session, 1, name, _config(), "x", "tester")


def test_create_source_requires_config(session, monkeypatch):
    monkeypatch.setattr(cdc, "_client", lambda: _client(
        lambda r: httpx.Response(200, json={})))
    with pytest.raises(ValueError, match="database"):
        cdc.create_source(session, 1, "bad-%s" % uuid.uuid4().hex[:6],
                          {"host": "h", "user": "u"}, "x", "tester")


def test_pause_and_resume_update_status(session, monkeypatch):
    def handler(request):
        if request.method == "PUT" and request.url.path.endswith("/pause"):
            return httpx.Response(202, json={})
        if request.method == "PUT" and request.url.path.endswith("/resume"):
            return httpx.Response(202, json={})
        if request.method == "PUT":
            return httpx.Response(201, json={})
        return httpx.Response(200, json={"connector": {"state": "RUNNING"},
                                         "tasks": []})

    monkeypatch.setattr(cdc, "_client", lambda: _client(handler))
    source = cdc.create_source(session, 1, "p-%s" % uuid.uuid4().hex[:6],
                               _config(), "x", "tester")

    cdc.pause_source(session, source, "tester")
    assert source.status == "paused"
    cdc.resume_source(session, source, "tester")
    assert source.status == "running"


def test_delete_source_removes_connector_and_row(session, monkeypatch):
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path))
        if request.method == "PUT":
            return httpx.Response(201, json={})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"connector": {"state": "RUNNING"},
                                         "tasks": []})

    monkeypatch.setattr(cdc, "_client", lambda: _client(handler))
    source = cdc.create_source(session, 1, "d-%s" % uuid.uuid4().hex[:6],
                               _config(), "x", "tester")
    source_id = source.id
    connector = source.connector_name
    cdc.delete_source(session, source, "tester")

    assert ("DELETE", "/connectors/" + connector) in seen
    assert session.get(CdcSource, source_id) is None


def test_status_maps_failure(session, monkeypatch):
    def handler(request):
        if request.method == "PUT":
            return httpx.Response(201, json={})
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={
                "connector": {"state": "FAILED", "trace": "boom"},
                "tasks": []})
        return httpx.Response(200, json={"connector": {"state": "RUNNING"},
                                         "tasks": []})

    monkeypatch.setattr(cdc, "_client", lambda: _client(handler))
    source = cdc.create_source(session, 1, "f-%s" % uuid.uuid4().hex[:6],
                               _config(), "x", "tester")
    out = cdc.refresh_status(session, source)
    assert out["status"] == "failed"


def test_unconfigured_debezium_raises():
    with pytest.raises(ValueError, match="not configured"):
        cdc._client()
