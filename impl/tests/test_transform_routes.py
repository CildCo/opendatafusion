import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from odf.db import SessionLocal
from odf.main import app
from odf.models import Datasource, User
from odf.services.approval import issue_token
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret


def _setup(tmp_path):
    url = "sqlite:///" + str(tmp_path / "route.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text, amount int)"))
        c.execute(text("insert into orders values (1,'a',10),(2,'b',7)"))
    with SessionLocal() as s:
        user = s.get(User, 9701)
        if not user:
            s.add(User(id=9701, username="model_user", password_hash="x",
                       role="admin", active=True))
        ds = Datasource(project_id=1, name="model_%s" % uuid.uuid4().hex[:6],
                        kind="sqlite", dsn_encrypted=encrypt_secret(url))
        s.add(ds)
        s.commit()
        return ds.id, create_token(9701, 1)


def _content(ds_id):
    return {"datasource_id": ds_id,
            "sql": "select city, sum(amount) as total from orders "
                   "group by city",
            "materialization": "table", "schema": "main",
            "unique_key": [], "layer": "mart", "description": "",
            "tests": [{"kind": "not_null", "column": "total"}],
            "columns": []}


def test_model_routes_create_preview_publish_and_run(tmp_path):
    ds_id, token = _setup(tmp_path)
    headers = {"Authorization": "Bearer " + token}
    client = TestClient(app)
    created = client.post("/api/v1/models", json={
        "name": "route model", "content": _content(ds_id)}, headers=headers)
    assert created.status_code == 200, created.text
    model_id = created.json()["id"]
    assert client.post(f"/api/v1/models/{model_id}/validate",
                       json={"content": _content(ds_id)},
                       headers=headers).json()["valid"] is True
    preview = client.post(f"/api/v1/models/{model_id}/preview",
                          json={"content": _content(ds_id), "limit": 10},
                          headers=headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["row_count"] == 2
    target = client.get(f"/api/v1/models/{model_id}/target",
                        headers=headers).json()
    assert target["schema"] == "main"
    published = client.post(
        f"/api/v1/models/{model_id}/publish",
        params={"approval_token": issue_token(model_id, "publish_model")},
        headers=headers)
    assert published.status_code == 200, published.text
    run = client.post(f"/api/v1/models/{model_id}/run", headers=headers)
    assert run.status_code == 200
    assert run.json()["job_id"]
    detail = client.get(f"/api/v1/models/{model_id}", headers=headers).json()
    assert detail["published_version"] == 1
    assert detail["enabled"] is True
