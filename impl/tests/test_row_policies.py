import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Project
from odf.services.crypto import encrypt_secret
from odf.services.policies import (create_policy, delete_policy,
                                   list_policies)
from odf.modelstudio.service import preview_dataset, query_metric


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "rp.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
        c.execute(text("insert into t values ('a',10),('a',5),('b',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="r1", name="r1", status=1))
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    ds = create_asset(s, 1, "dataset", "D", {
        "mode": "visual", "query": {"datasource_id": 1, "table": "t",
                                    "select": [{"column": "city"},
                                               {"column": "amount"}],
                                    "limit": 100},
        "params": [], "sql": None, "auth": None}, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mc = {"dataset_id": ds.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return s, ds.id, m.id


def test_policy_filters_dataset_and_metric(tmp_path):
    s, dsid, mid = _env(tmp_path)
    out = create_policy(s, 1, dsid, "city", "=", "a", ["viewer"], "admin")
    assert out["column"] == "city"
    assert len(list_policies(s, 1, dsid)) == 1
    d = preview_dataset(s, dsid, role="viewer")
    assert d["row_count"] == 2
    assert {r["city"] for r in d["rows"]} == {"a"}
    assert preview_dataset(s, dsid, role="editor")["row_count"] == 3
    assert preview_dataset(s, dsid, role="admin")["row_count"] == 3
    m = query_metric(s, mid, role="viewer")
    assert m["rows"] == [{"city": "a", "value": 15}]
    assert len(query_metric(s, mid, role="editor")["rows"]) == 2
    delete_policy(s, 1, dsid, out["id"], "admin")
    assert preview_dataset(s, dsid, role="viewer")["row_count"] == 3


def test_policy_validation(tmp_path):
    s, dsid, _ = _env(tmp_path)
    for args in (("nope", "=", "a", ["viewer"]),
                 ("city", "bogus", "a", ["viewer"]),
                 ("city", "=", "a", ["owner"]),
                 ("city", "in", [], ["viewer"])):
        with pytest.raises(ValueError):
            create_policy(s, 1, dsid, *args, actor="admin")


def test_policy_route(tmp_path):
    s, dsid, _ = _env(tmp_path)
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import User
    from odf.services.auth import create_token
    from odf.assets.service import create_asset as make
    from odf.assets.service import publish_asset as pub
    from odf.models import Datasource
    from odf.services.crypto import encrypt_secret
    url = "sqlite:///" + str(tmp_path / "route.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
    with SessionLocal() as g:
        ds = g.get(Datasource, 601)
        if ds:
            ds.dsn_encrypted = encrypt_secret(url)
        else:
            g.add(Datasource(id=601, project_id=1, name="rp",
                             kind="sqlite", dsn_encrypted=encrypt_secret(url)))
        g.commit()
        u = g.get(User, 1)
        if not u:
            u = User(id=1, username="rp", password_hash="x", role="admin",
                     active=True)
            g.add(u)
        u.role = "admin"
        u.active = True
        g.commit()
        a = make(g, 1, "dataset", "RP", {
            "mode": "visual", "query": {"datasource_id": 601, "table": "t",
                                        "select": [{"column": "city"},
                                                   {"column": "amount"}],
                                        "limit": 100},
            "params": [], "sql": None, "auth": None}, "admin", enabled=False)
        pub(g, a.id, "admin")
        aid = a.id
    def _role(role):
        with SessionLocal() as g:
            u = g.get(User, 1)
            u.role = role
            g.commit()

    c = TestClient(app)
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    r = c.post(f"/api/v1/datasets/{aid}/policies",
               json={"column": "city", "op": "=", "value": "a",
                     "roles": ["viewer"]}, headers=h)
    assert r.status_code == 200
    assert c.get(f"/api/v1/datasets/{aid}/policies",
                 headers=h).status_code == 200
    _role("viewer")
    assert c.post(f"/api/v1/datasets/{aid}/preview",
                  json={}, headers=h).status_code == 403
    _role("admin")
    assert c.delete(f"/api/v1/datasets/{aid}/policies/{r.json()['id']}",
                    headers=h).status_code == 200
