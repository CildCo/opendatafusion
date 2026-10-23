from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.auth import create_token


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="model_u%d" % uid,
                     password_hash="x", role=role, active=True)
            s.add(u)
        else:
            u.role = role
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_dataset_and_metric_routes():
    _user(1, "admin")
    c = TestClient(app)
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "id"}]}, "params": [], "sql": None,
        "auth": None}
    r = c.post("/api/v1/datasets", json={"name": "D", "content": content},
               headers=_h())
    assert r.status_code == 200
    did = r.json()["id"]
    assert c.get(f"/api/v1/datasets/{did}", headers=_h()).status_code == 200
    assert c.get(f"/api/v1/datasets/{did}/schema",
                 headers=_h()).status_code in (200, 400)
    metric = {"dataset_id": did,
              "measure": {"agg": "count", "column": "*", "as": "value"},
              "dimensions": [], "filters": [],
              "format": {"type": "number"}}
    r = c.post("/api/v1/metrics", json={"name": "M", "content": metric},
               headers=_h())
    assert r.status_code == 200
    mid = r.json()["id"]
    assert c.get(f"/api/v1/metrics/{mid}", headers=_h()).status_code == 200


def test_model_routes_are_project_scoped_and_role_gated():
    from odf.assets.service import create_asset
    from odf.db import SessionLocal
    _user(1, "admin")
    _user(2, "viewer")
    content = {"mode": "visual", "query": {
        "datasource_id": 1, "table": "t",
        "select": [{"column": "id"}]}, "params": []}
    with SessionLocal() as s:
        other = create_asset(s, 2, "dataset", "other", content, "admin",
                             enabled=False)
        oid = other.id
    c = TestClient(app)
    assert c.get(f"/api/v1/datasets/{oid}",
                 headers=_h(1, 1)).status_code == 404
    assert c.post("/api/v1/datasets", json={"name": "v", "content": content},
                  headers=_h(2, 1)).status_code == 403
    r = c.post("/api/v1/mcp/dataset_schema", json={"asset_id": oid},
               headers=_h(1, 1))
    assert r.status_code == 403
