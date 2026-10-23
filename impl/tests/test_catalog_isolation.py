import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import Column, Dataset, Datasource, Project, Tag, User
from odf.services.auth import create_token
from odf.services.catalog import dataset_detail, tag_dataset
from odf.services.crypto import encrypt_secret


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    return s


def test_service_rejects_cross_project_detail_and_tag():
    s = _session()
    s.add_all([
        Datasource(id=1, project_id=1, name="a", kind="sqlite",
                   dsn_encrypted="x"),
        Datasource(id=2, project_id=2, name="b", kind="sqlite",
                   dsn_encrypted="x"),
    ])
    s.add_all([
        Dataset(id=1, datasource_id=1, schema_name="main", table_name="t1"),
        Dataset(id=2, datasource_id=2, schema_name="main", table_name="t2"),
    ])
    s.add(Column(id=1, dataset_id=1, name="id", data_type="INTEGER"))
    s.add(Tag(id=1, project_id=1, name="one"))
    s.commit()
    assert dataset_detail(s, 1, project_id=1)["table"] == "t1"
    assert dataset_detail(s, 1, project_id=2) is None
    with pytest.raises(ValueError):
        tag_dataset(s, 1, 1, project_id=2)
    t2 = Tag(project_id=2, name="two")
    s.add(t2)
    s.commit()
    with pytest.raises(ValueError):
        tag_dataset(s, 1, t2.id, project_id=1)


def test_catalog_routes_ignore_other_project_ids():
    with SessionLocal() as s:
        for pid in (1, 2):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code="iso%d" % pid, name="iso",
                              status=1))
            for did, name in ((910 + pid, "iso-ds-%d" % pid),):
                ds = s.get(Datasource, did)
                if ds:
                    ds.project_id = pid
                    ds.kind = "sqlite"
                    ds.dsn_encrypted = encrypt_secret("sqlite://")
                else:
                    s.add(Datasource(id=did, project_id=pid, name=name,
                                     kind="sqlite",
                                     dsn_encrypted=encrypt_secret(
                                         "sqlite://")))
        s.commit()
        for did, pid, table in ((9101, 1, "only_one"),
                                (9102, 2, "only_two")):
            dsid = 910 + pid
            d = s.get(Dataset, did)
            if d:
                d.datasource_id = dsid
                d.table_name = table
            else:
                s.add(Dataset(id=did, datasource_id=dsid,
                              schema_name="main", table_name=table))
        t = s.query(Tag).filter_by(project_id=2, name="other-tag").first()
        if not t:
            t = Tag(project_id=2, name="other-tag")
            s.add(t)
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="iso", password_hash="x", role="admin",
                     active=True)
            s.add(u)
        u.role, u.active = "admin", True
        s.commit()
        other_tag = t.id
        other_dataset = 9102
    c = TestClient(app)
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    rows = c.get("/api/v1/catalog/datasets?project_id=2", headers=h).json()
    assert [r["id"] for r in rows] == [9101]
    assert c.get(f"/api/v1/catalog/datasets/{other_dataset}",
                 headers=h).status_code == 404
    view = c.get("/api/v1/catalog/lineage?project_id=2", headers=h).json()
    assert all(not n.startswith("911:") for n in view["nodes"])
    assert c.post("/api/v1/catalog/tags",
                  json={"project_id": 2, "name": "leak"}, headers=h
                  ).status_code == 403
    assert c.post("/api/v1/catalog/tags/attach",
                  json={"dataset_id": 9101, "tag_id": other_tag},
                  headers=h).status_code in (400, 404)


def test_mcp_datasource_tools_are_project_scoped():
    from odf.mcp.server import CURRENT_PROJECT, TOOLS
    with SessionLocal() as s:
        ds = s.get(Datasource, 920)
        if not ds:
            s.add(Datasource(id=920, project_id=2, name="mcp-other",
                             kind="sqlite",
                             dsn_encrypted=encrypt_secret("sqlite://")))
            s.commit()
    token = CURRENT_PROJECT.set(1)
    try:
        with pytest.raises(PermissionError):
            TOOLS["query_sql"](datasource_id=920, sql="select 1")
        rows = TOOLS["list_datasources"]()
        assert all(r["id"] != 920 for r in rows)
        assert TOOLS["test_datasource"](datasource_id=920)["ok"] is False
    finally:
        CURRENT_PROJECT.reset(token)
