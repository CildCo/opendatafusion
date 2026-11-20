import sqlite3
import uuid

import pytest

from odf.db import SessionLocal
from odf.models import (Column, ColumnPolicy, Dataset, Datasource, Project,
                        QualityResult, QualityRule, User)
from odf.services import catalog as catalog_service
from odf.services.crypto import encrypt_secret

PROJECT_ID = 914


@pytest.fixture()
def dataset(tmp_path):
    with SessionLocal() as s:
        if not s.get(Project, PROJECT_ID):
            s.add(Project(id=PROJECT_ID, code="catalog-detail",
                          name="Catalog detail", status=1))
            s.commit()
        db = tmp_path / "sample.db"
        con = sqlite3.connect(db)
        con.execute("create table users (id integer, email text)")
        con.executemany("insert into users values (?, ?)",
                        [(1, "a@example.com"), (2, "b@example.com")])
        con.commit()
        con.close()
        ds = Datasource(project_id=PROJECT_ID,
                        name="cat-%s" % uuid.uuid4().hex[:8],
                        kind="sqlite",
                        dsn_encrypted=encrypt_secret("sqlite:///%s" % db))
        s.add(ds)
        s.commit()
        d = Dataset(datasource_id=ds.id, schema_name="main",
                    table_name="users")
        s.add(d)
        s.commit()
        s.add_all([Column(dataset_id=d.id, name="id", data_type="INTEGER"),
                   Column(dataset_id=d.id, name="email", data_type="TEXT")])
        s.commit()
        ids = (d.id, ds.id)
    yield ids
    with SessionLocal() as s:
        d = s.get(Dataset, ids[0])
        s.query(ColumnPolicy).filter_by(datasource_id=ids[1]).delete()
        s.query(QualityResult).filter(
            QualityResult.rule_id.in_(
                s.query(QualityRule.id).filter_by(dataset_id=ids[0]))
        ).delete(synchronize_session=False)
        s.query(QualityRule).filter_by(dataset_id=ids[0]).delete()
        s.query(Column).filter_by(dataset_id=ids[0]).delete()
        if d:
            s.delete(d)
        ds = s.get(Datasource, ids[1])
        if ds:
            s.delete(ds)
        s.commit()


def test_detail_carries_source_and_stats(dataset):
    dataset_id, _ = dataset
    with SessionLocal() as s:
        rule = QualityRule(project_id=PROJECT_ID, dataset_id=dataset_id,
                           name="not-null-id", kind="not_null",
                           column_name="id")
        s.add(rule)
        s.commit()
        s.add(QualityResult(rule_id=rule.id, status="pass", detail_json={}))
        s.commit()
        detail = catalog_service.dataset_detail(s, dataset_id, PROJECT_ID)
    assert detail["schema"] == "main"
    assert detail["table"] == "users"
    assert detail["datasource_kind"] == "sqlite"
    assert detail["datasource_name"].startswith("cat-")
    assert detail["stats"]["column_count"] == 2
    assert detail["stats"]["rule_count"] == 1
    assert detail["stats"]["last_quality"]["status"] == "pass"


def test_sample_masks_governed_columns(dataset):
    dataset_id, datasource_id = dataset
    with SessionLocal() as s:
        s.add(ColumnPolicy(project_id=PROJECT_ID,
                           datasource_id=datasource_id,
                           schema_name="main", table_name="users",
                           column_name="email", classification="pii",
                           mask_type="redact", exempt_roles_json=[],
                           created_by="tester"))
        s.commit()
        masked = catalog_service.dataset_sample(
            s, PROJECT_ID, dataset_id, limit=10, role="viewer",
            actor="tester")
        assert masked["row_count"] == 2
        assert {r["email"] for r in masked["rows"]} == {"***"}
        assert {r["id"] for r in masked["rows"]} == {1, 2}

        raw = catalog_service.dataset_sample(
            s, PROJECT_ID, dataset_id, limit=10, role="admin", actor="tester")
        assert {r["email"] for r in raw["rows"]} == {"a@example.com",
                                                    "b@example.com"}


def test_sample_is_project_scoped(dataset):
    dataset_id, _ = dataset
    with SessionLocal() as s:
        with pytest.raises(ValueError):
            catalog_service.dataset_sample(s, 9999, dataset_id)


def test_sample_rejects_unsafe_identifiers(dataset):
    dataset_id, _ = dataset
    with SessionLocal() as s:
        d = s.get(Dataset, dataset_id)
        d.table_name = "users; drop table users"
        s.commit()
        with pytest.raises(ValueError):
            catalog_service.dataset_sample(s, PROJECT_ID, dataset_id)


def test_history_records_dataset_events(dataset):
    dataset_id, _ = dataset
    with SessionLocal() as s:
        catalog_service.dataset_sample(s, PROJECT_ID, dataset_id,
                                       role="viewer", actor="tester")
        rows = catalog_service.dataset_history(s, PROJECT_ID, dataset_id)
    assert any(r["action"] == "dataset_sample" for r in rows)
    assert rows[0]["actor"] == "tester"


def test_history_ignores_other_objects_with_the_same_id(dataset):
    from odf.models import AuditLog

    dataset_id, _ = dataset
    with SessionLocal() as s:
        s.add(AuditLog(actor="tester", action="engine_job_finished",
                       target=str(dataset_id), detail_json={}))
        s.commit()
        rows = catalog_service.dataset_history(s, PROJECT_ID, dataset_id)
    assert all(r["action"] != "engine_job_finished" for r in rows)


def _user(user_id, username):
    with SessionLocal() as s:
        u = s.get(User, user_id)
        if not u:
            s.add(User(id=user_id, username=username, password_hash="x",
                       role="admin", active=True))
            s.commit()


def test_sample_routes_are_project_scoped(dataset):
    from fastapi.testclient import TestClient

    from odf.main import app
    from odf.services.auth import create_token

    dataset_id, _ = dataset
    _user(914, "catalog-detail")
    client = TestClient(app)
    own = {"Authorization": "Bearer " + create_token(914, PROJECT_ID)}
    other = {"Authorization": "Bearer " + create_token(914, 9999)}
    ok = client.get(
        f"/api/v1/catalog/datasets/{dataset_id}/sample?limit=5", headers=own)
    assert ok.status_code == 200
    assert ok.json()["row_count"] == 2
    assert client.get(
        f"/api/v1/catalog/datasets/{dataset_id}/sample",
        headers=other).status_code == 404
    assert client.get(
        f"/api/v1/catalog/datasets/{dataset_id}/history",
        headers=own).status_code == 200
    assert client.get(
        f"/api/v1/catalog/datasets/{dataset_id}/history",
        headers=other).status_code == 404


def test_profile_reports_nulls_distinct_and_range(dataset):
    dataset_id, _ = dataset
    with SessionLocal() as s:
        out = catalog_service.dataset_profile(s, PROJECT_ID, dataset_id,
                                              sample=1000, role="admin")
    by_name = {c["name"]: c for c in out["columns"]}
    assert out["rows"] == 2
    assert by_name["id"]["nulls"] == 0
    assert by_name["id"]["distinct"] == 2
    assert int(by_name["id"]["min"]) == 1
    assert int(by_name["id"]["max"]) == 2


def test_profile_hides_ranges_for_masked_columns(dataset):
    dataset_id, datasource_id = dataset
    with SessionLocal() as s:
        policy = (s.query(ColumnPolicy)
                  .filter_by(datasource_id=datasource_id).first())
        if not policy:
            s.add(ColumnPolicy(project_id=PROJECT_ID,
                               datasource_id=datasource_id,
                               schema_name="main", table_name="users",
                               column_name="email", classification="pii",
                               mask_type="redact", exempt_roles_json=[],
                               created_by="tester"))
            s.commit()
        masked = catalog_service.dataset_profile(
            s, PROJECT_ID, dataset_id, sample=1000, role="viewer")
        email = next(c for c in masked["columns"] if c["name"] == "email")
        assert email["masked"] is True
        assert email["min"] is None and email["max"] is None
        raw = catalog_service.dataset_profile(
            s, PROJECT_ID, dataset_id, sample=1000, role="admin")
        email = next(c for c in raw["columns"] if c["name"] == "email")
        assert email["min"] == "a@example.com"


def test_profile_is_project_scoped(dataset):
    dataset_id, _ = dataset
    with SessionLocal() as s:
        with pytest.raises(ValueError):
            catalog_service.dataset_profile(s, 9999, dataset_id)
