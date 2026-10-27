import json
import uuid

import httpx
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.auth import create_token


def _headers(uid, role="editor", project_id=1):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="cdc_%d" % uid, password_hash="x",
                        role=role, active=True)
            s.add(user)
        else:
            user.role = role
            user.active = True
        s.commit()
    return {"Authorization": "Bearer " + create_token(uid, project_id)}


def _config():
    return {"host": "cdc-postgres.stream.svc", "database": "cdc",
            "user": "cdc", "table_list": "public.events"}


def _fake_debezium(monkeypatch):
    def handler(request):
        if request.method == "PUT" and request.url.path.endswith("/pause"):
            return httpx.Response(202, json={})
        if request.method == "PUT" and request.url.path.endswith("/resume"):
            return httpx.Response(202, json={})
        if request.method == "PUT":
            return httpx.Response(201, json={})
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.url.path.endswith("/status"):
            return httpx.Response(200, json={
                "connector": {"state": "RUNNING"}, "tasks": [{"id": 0}]})
        return httpx.Response(200, json={"connector": {"state": "RUNNING"},
                                         "tasks": []})

    monkeypatch.setattr(
        "odf.cdc.service._client",
        lambda: httpx.Client(base_url="http://debezium",
                             transport=httpx.MockTransport(handler)))


def test_viewer_cannot_create_cdc_source():
    response = TestClient(app).post(
        "/api/v1/cdc/sources",
        headers=_headers(951, role="viewer"),
        json={"name": "v-%s" % uuid.uuid4().hex[:6], "config": _config(),
              "password": "x"})
    assert response.status_code == 403


def test_create_source_returns_connector_without_secret(monkeypatch):
    _fake_debezium(monkeypatch)
    response = TestClient(app).post(
        "/api/v1/cdc/sources", headers=_headers(952),
        json={"name": "orders-%s" % uuid.uuid4().hex[:6],
              "config": _config(), "password": "s3cret"})
    assert response.status_code == 201
    body = response.json()
    assert body["connector_name"].startswith("odf-p1-")
    assert body["status"] == "running"
    assert "s3cret" not in json.dumps(body)


def test_create_requires_debezium_configuration():
    response = TestClient(app).post(
        "/api/v1/cdc/sources", headers=_headers(953),
        json={"name": "un-%s" % uuid.uuid4().hex[:6], "config": _config(),
              "password": "x"})
    assert response.status_code == 503


def test_get_source_from_other_project_is_404(monkeypatch):
    _fake_debezium(monkeypatch)
    client = TestClient(app)
    created = client.post(
        "/api/v1/cdc/sources", headers=_headers(954, project_id=1),
        json={"name": "iso-%s" % uuid.uuid4().hex[:6], "config": _config(),
              "password": "x"}).json()

    response = client.get("/api/v1/cdc/sources/%d" % created["id"],
                          headers=_headers(954, project_id=2))
    assert response.status_code == 404


def test_list_sources_is_project_scoped(monkeypatch):
    _fake_debezium(monkeypatch)
    client = TestClient(app)
    mine = "mine-%s" % uuid.uuid4().hex[:6]
    other = "other-%s" % uuid.uuid4().hex[:6]
    client.post("/api/v1/cdc/sources", headers=_headers(955, project_id=1),
                json={"name": mine, "config": _config(), "password": "x"})
    client.post("/api/v1/cdc/sources", headers=_headers(955, project_id=2),
                json={"name": other, "config": _config(), "password": "x"})

    rows = client.get("/api/v1/cdc/sources",
                      headers=_headers(955, project_id=1)).json()
    names = [r["name"] for r in rows]
    assert mine in names
    assert other not in names


def test_pause_resume_and_delete(monkeypatch):
    _fake_debezium(monkeypatch)
    client = TestClient(app)
    headers = _headers(956)
    created = client.post(
        "/api/v1/cdc/sources", headers=headers,
        json={"name": "life-%s" % uuid.uuid4().hex[:6], "config": _config(),
              "password": "x"}).json()

    paused = client.post("/api/v1/cdc/sources/%d/pause" % created["id"],
                         headers=headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post("/api/v1/cdc/sources/%d/resume" % created["id"],
                          headers=headers)
    assert resumed.json()["status"] == "running"

    deleted = client.delete("/api/v1/cdc/sources/%d" % created["id"],
                            headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/v1/cdc/sources/%d" % created["id"],
                      headers=headers).status_code == 404


def test_duplicate_name_returns_409(monkeypatch):
    _fake_debezium(monkeypatch)
    client = TestClient(app)
    headers = _headers(957)
    name = "dup-%s" % uuid.uuid4().hex[:6]
    body = {"name": name, "config": _config(), "password": "x"}
    assert client.post("/api/v1/cdc/sources", headers=headers,
                       json=body).status_code == 201
    assert client.post("/api/v1/cdc/sources", headers=headers,
                       json=body).status_code == 409
