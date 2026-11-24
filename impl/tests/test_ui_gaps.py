from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import (Asset, AssetVersion, Project, ProjectMember, User)
from odf.services.auth import create_token


def _admin():
    with SessionLocal() as s:
        u = s.query(User).filter_by(username="admin").first()
        if not u:
            u = User(username="admin", role="admin", active=True,
                     password_hash="x")
            s.add(u)
            s.commit()
        return u.id


def _project(pid):
    with SessionLocal() as s:
        if not s.get(Project, pid):
            s.add(Project(id=pid, code="gap%d" % pid, name="gap"))
            s.commit()


def _headers(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_totp_setup_accepts_an_empty_body():
    uid = _admin()
    c = TestClient(app)
    r = c.post("/api/v1/auth/totp/setup", json={},
               headers=_headers(uid))
    assert r.status_code == 200
    assert r.json()["secret"]


def test_dashboard_counts_published_api_assets():
    _project(913)
    with SessionLocal() as s:
        stale = s.query(Asset).filter_by(key="gap_api").all()
        ids = [a.id for a in s.query(Asset).filter_by(project_id=913,
                                                      type="api").all()]
        ids += [a.id for a in stale]
        if ids:
            s.query(AssetVersion).filter(
                AssetVersion.asset_id.in_(ids)).delete(
                    synchronize_session=False)
            s.query(Asset).filter(
                Asset.id.in_(ids)).delete(synchronize_session=False)
        s.commit()
        a = Asset(project_id=913, type="api", key="gap_api", name="gap api",
                  owner="1")
        s.add(a)
        s.commit()
        aid = a.id
    uid = _admin()
    c = TestClient(app)
    before = c.get("/api/v1/dashboard", headers=_headers(uid, 913)).json()
    assert before["apis"] == 0
    with SessionLocal() as s:
        version = AssetVersion(asset_id=aid, version=1, content_json={},
                               status="published", created_by="1")
        s.add(version)
        s.flush()
        s.get(Asset, aid).published_version_id = version.id
        s.commit()
    after = c.get("/api/v1/dashboard", headers=_headers(uid, 913)).json()
    assert after["apis"] == 1


def test_engine_profiles_mask_secret_values(monkeypatch):
    import odf.api.engine as engine_api

    monkeypatch.setattr(
        engine_api, "engine_profiles",
        lambda settings: {
            "lakehouse_enabled": True,
            "spark": {"image": "img", "spark_conf": {
                "spark.sql.catalog.iceberg.s3.secret-access-key": "topsecret",
                "spark.sql.catalog.iceberg.s3.access-key-id": "odf",
                "spark.executor.memory": "1g"}},
            "flink": {"sql_gateway": True, "rest": True}})
    r = TestClient(app).get("/api/v1/engine/profiles", headers=_headers())
    assert r.status_code == 200
    conf = r.json()["spark"]["spark_conf"]
    assert conf["spark.sql.catalog.iceberg.s3.secret-access-key"] == "***"
    assert conf["spark.sql.catalog.iceberg.s3.access-key-id"] == "***"
    assert conf["spark.executor.memory"] == "1g"


def test_engine_error_hides_gateway_urls():
    from odf.api.engine import _error

    error = _error(ValueError(
        "engine submission failed: Server error '500 Internal Server Error' "
        "for url 'http://198.51.100.7:30083/v1/sessions/x/result/0'"))
    assert error.status_code == 502
    assert "198.51.100" not in (error.detail or "")
    assert "http" not in (error.detail or "")


def test_submission_failure_keeps_reason_but_drops_transport():
    from odf.services.engine_jobs import _public_error

    leaked = _public_error(RuntimeError(
        "Server error '500 Internal Server Error' for url "
        "'http://198.51.100.9:30083/v1/sessions/x'"))
    assert "http" not in leaked
    assert _public_error(ValueError("flink did not return a job id")) == \
        "flink did not return a job id"


def test_catalog_tag_can_be_detached():
    import uuid

    from odf.models import Dataset, Datasource
    from odf.services.catalog import (create_tag, dataset_detail, tag_dataset,
                                      untag_dataset)
    from odf.services.crypto import encrypt_secret

    _project(913)
    with SessionLocal() as s:
        ds = Datasource(project_id=913, name="tag-%s" % uuid.uuid4().hex[:6],
                        kind="sqlite",
                        dsn_encrypted=encrypt_secret("sqlite:////tmp/x.db"))
        s.add(ds)
        s.commit()
        d = Dataset(datasource_id=ds.id, schema_name="main", table_name="t")
        s.add(d)
        s.commit()
        try:
            tag = create_tag(s, 913, "ui-tag")
            tag_dataset(s, d.id, tag.id, 913)
            assert tag.name in dataset_detail(s, d.id)["tags"]
            untag_dataset(s, d.id, tag.id, 913)
            assert dataset_detail(s, d.id)["tags"] == []
        finally:
            s.query(Dataset).filter_by(id=d.id).delete()
            s.delete(ds)
            s.commit()


def test_project_members_can_be_removed():
    _project(913)
    with SessionLocal() as s:
        u = s.query(User).filter_by(username="gap_member").first()
        if not u:
            u = User(username="gap_member", role="viewer", active=True,
                     password_hash="x")
            s.add(u)
            s.commit()
        uid = u.id
        s.query(ProjectMember).filter_by(project_id=913,
                                         user_id=uid).delete()
        s.add(ProjectMember(project_id=913, user_id=uid, role="viewer"))
        s.commit()
    admin = _admin()
    c = TestClient(app)
    r = c.delete("/api/v1/projects/913/members/%d" % uid,
                 headers=_headers(admin))
    assert r.status_code == 204
    left = c.get("/api/v1/projects/913/members", headers=_headers(admin))
    assert all(m["user_id"] != uid for m in left.json())
