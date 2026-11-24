from datetime import datetime, timezone

from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import (Alert, Asset, AssetVersion, Dataset, Datasource,
                        Job, PipelineNodeRun, Project, QualityRule, User)
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret


def _seed():
    now = datetime.now(timezone.utc)
    with SessionLocal() as s:
        for pid, code in ((8201, "dash1"), (8202, "dash2")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        for uid, name in ((8201, "dash_user_1"), (8202, "dash_user_2")):
            if not s.get(User, uid):
                s.add(User(id=uid, username=name, password_hash="x",
                           role="viewer", active=True))
        for pid in (8201, 8202):
            if not s.get(Datasource, pid):
                s.add(Datasource(id=pid, project_id=pid, name="ds%d" % pid,
                                 kind="sqlite",
                                 dsn_encrypted=encrypt_secret("sqlite://")))
            pipe_id = 8211 if pid == 8201 else 8212
            s.query(PipelineNodeRun).filter_by(asset_id=pipe_id).delete()
            s.query(Job).filter_by(asset_id=pipe_id).delete()
            s.query(Asset).filter_by(id=pipe_id).delete()
            s.add(Asset(id=pipe_id, project_id=pid, type="pipeline",
                        key="pipeline_%d" % pid,
                        name="中文管道" if pid == 8201 else "pipeline_%d" % pid,
                        owner="tester", enabled=True))
            s.flush()
            s.add(Job(asset_id=pipe_id, asset_type="pipeline",
                      status="success", created_at=now, finished_at=now,
                      attempts=1))
            if pid == 8201:
                s.add(Job(asset_id=pipe_id, asset_type="pipeline",
                          status="success", created_at=now,
                          finished_at=now, attempts=1))
            # Published API assets are what the interface counter reports.
            old = s.query(Asset).filter_by(project_id=pid, type="api").all()
            for row in old:
                s.query(AssetVersion).filter_by(asset_id=row.id).delete(
                    synchronize_session=False)
                s.delete(row)
            s.flush()
            api = Asset(project_id=pid, type="api", key="api_%d" % pid,
                        name="api%d" % pid, owner="1", enabled=True)
            s.add(api)
            s.flush()
            version = AssetVersion(asset_id=api.id, version=1,
                                   content_json={}, status="published",
                                   created_by="1")
            s.add(version)
            s.flush()
            api.published_version_id = version.id
            if not s.get(Dataset, pid):
                s.add(Dataset(id=pid, datasource_id=pid, schema_name="main",
                              table_name="t%d" % pid))
            if not s.get(QualityRule, pid):
                s.add(QualityRule(id=pid, project_id=pid, dataset_id=pid,
                                  name="qr%d" % pid, kind="not_null",
                                  column_name="v", config_json={},
                                  enabled=True))
            s.query(Alert).filter_by(title="alert_%d" % pid).delete()
            s.add(Alert(project_id=pid, severity="warning",
                        title="alert_%d" % pid, detail_json={},
                        status="open"))
        s.flush()
        for job in s.query(Job).filter_by(asset_id=8211).all():
            s.add(PipelineNodeRun(job_id=job.id, asset_id=8211,
                                  node_id="src", status="success",
                                  in_num=0, out_num=5, ms=10))
            s.add(PipelineNodeRun(job_id=job.id, asset_id=8211,
                                  node_id="sink", status="success",
                                  in_num=5, out_num=5, ms=10))
        s.commit()


def _h(uid, project):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_dashboard_counts_are_project_scoped():
    _seed()
    c = TestClient(app)
    other = c.get("/api/v1/dashboard", headers=_h(8202, 8202)).json()
    assert other["datasources"] == 1
    assert other["pipelines"] == 1
    assert other["apis"] == 1
    assert other["quality_rules"] == 1
    assert other["open_alerts"] == 1

    own = c.get("/api/v1/dashboard", headers=_h(8201, 8201)).json()
    assert own["datasources"] == 1
    assert own["pipelines"] == 1
    assert own["quality_rules"] == 1
    assert own["open_alerts"] == 1
    assert own["runs_24h"] == 2


def test_dashboard_recent_runs_include_pipeline_and_stay_scoped():
    _seed()
    c = TestClient(app)
    own = c.get("/api/v1/dashboard", headers=_h(8201, 8201)).json()
    names = [r["target"] for r in own["recent_runs"]]
    assert "中文管道" in names
    pipe = next(r for r in own["recent_runs"] if r["target"] == "中文管道")
    assert pipe["status"] == 2
    assert pipe["in"] == 5 and pipe["out"] == 5
    assert pipe["asset_id"] == 8211

    other = c.get("/api/v1/dashboard", headers=_h(8202, 8202)).json()
    names = [r["target"] for r in other["recent_runs"]]
    assert "中文管道" not in names
    assert "pipeline_8202" in names


def test_pipeline_jobs_expose_node_trace():
    _seed()
    r = TestClient(app).get("/api/v1/pipelines/8211/jobs",
                            headers=_h(8201, 8201))
    assert r.status_code == 200
    jobs = r.json()
    assert jobs and jobs[0]["nodes"]
    nodes = {row["node_id"]: row for row in jobs[0]["nodes"]}
    assert nodes["src"]["out_num"] == 5
    assert nodes["sink"]["in_num"] == 5
    assert nodes["sink"]["status"] == "success"
