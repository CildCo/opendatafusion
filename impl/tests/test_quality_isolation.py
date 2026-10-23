from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import (Column, Dataset, Datasource, Project, ProjectMember,
                        QualityRule, User)
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret


def _seed():
    with SessionLocal() as s:
        for pid, code in ((8101, "q1"), (8102, "q2")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        for uid, name, role in ((8101, "q_viewer_1", "viewer"),
                                (8102, "q_editor_2", "editor"),
                                (8103, "q_editor_1", "editor")):
            if not s.get(User, uid):
                s.add(User(id=uid, username=name, password_hash="x",
                           role=role, active=True))
        for pid, uid in ((8101, 8101), (8102, 8102), (8101, 8103)):
            if not (s.query(ProjectMember)
                    .filter_by(project_id=pid, user_id=uid).first()):
                s.add(ProjectMember(project_id=pid, user_id=uid,
                                    role="viewer" if uid == 8101 else "editor"))
        if not s.get(Datasource, 8101):
            s.add(Datasource(id=8101, project_id=8101, name="q ds",
                             kind="sqlite",
                             dsn_encrypted=encrypt_secret("sqlite://")))
        if not s.get(Dataset, 8101):
            s.add(Dataset(id=8101, datasource_id=8101, schema_name="main",
                          table_name="q_table"))
            s.add(Column(id=8101, dataset_id=8101, name="v",
                         data_type="TEXT"))
        if not s.get(QualityRule, 8101):
            s.add(QualityRule(id=8101, project_id=8101, dataset_id=8101,
                              name="q rule", kind="not_null",
                              column_name="v", config_json={},
                              enabled=True))
        s.commit()


def _h(uid, project):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_quality_rules_are_scoped_to_token_project():
    _seed()
    c = TestClient(app)
    r = c.get("/api/v1/quality/rules", headers=_h(8102, 8102))
    assert r.status_code == 200
    assert all(x["id"] != 8101 for x in r.json())

    r = c.get("/api/v1/quality/rules?project_id=8101",
              headers=_h(8102, 8102))
    assert r.status_code == 200
    assert all(x["id"] != 8101 for x in r.json())

    r = c.get("/api/v1/quality/rules", headers=_h(8101, 8101))
    assert r.status_code == 200
    assert any(x["id"] == 8101 for x in r.json())


def test_viewer_cannot_create_quality_rule():
    _seed()
    r = TestClient(app).post(
        "/api/v1/quality/rules", headers=_h(8101, 8101),
        json={"dataset_id": 8101, "name": "nope", "kind": "not_null",
              "column_name": "v", "config": {}})
    assert r.status_code == 403


def test_editor_cannot_create_rule_on_other_project_dataset():
    _seed()
    c = TestClient(app)
    r = c.post("/api/v1/quality/rules", headers=_h(8102, 8102),
               json={"dataset_id": 8101, "name": "cross", "kind": "not_null",
                     "column_name": "v", "config": {}})
    assert r.status_code == 404

    r = c.post("/api/v1/quality/rules", headers=_h(8102, 8102),
               json={"project_id": 8101, "dataset_id": 8101,
                     "name": "cross", "kind": "not_null",
                     "column_name": "v", "config": {}})
    assert r.status_code == 403


def test_cross_project_run_and_results_are_hidden():
    _seed()
    c = TestClient(app)
    assert c.post("/api/v1/quality/rules/8101/run",
                  headers=_h(8102, 8102)).status_code == 404
    assert c.get("/api/v1/quality/rules/8101/results",
                 headers=_h(8102, 8102)).status_code == 404


def test_editor_can_create_rule_in_own_project():
    _seed()
    c = TestClient(app)
    r = c.post("/api/v1/quality/rules", headers=_h(8103, 8101),
               json={"project_id": 8101, "dataset_id": 8101,
                     "name": "own rule", "kind": "not_null",
                     "column_name": "v", "config": {}})
    assert r.status_code == 200
    rid = r.json()["id"]
    assert any(x["id"] == rid for x in
               c.get("/api/v1/quality/rules", headers=_h(8103, 8101)).json())
