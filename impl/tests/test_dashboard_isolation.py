from datetime import datetime, timezone

from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import (Alert, Asset, Dataset, Datasource, Flow, FlowRun,
                        Interface, Job, PipelineNodeRun, Project,
                        QualityRule, User)
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
            if not s.get(Flow, pid):
                s.add(Flow(id=pid, project_id=pid, name="flow_%d" % pid,
                           status=0))
            if not s.get(Interface, pid):
                s.add(Interface(id=pid, project_id=pid, datasource_id=pid,
                                interface_key="if_%d" % pid,
                                name="if%d" % pid, sql_text="select 1",
                                status=1))
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
        # flow run in each project
        s.query(FlowRun).filter(FlowRun.flow_id.in_((8201, 8202))).delete(
            synchronize_session=False)
        for pid, rows in ((8201, 3), (8202, 7)):
            s.add(FlowRun(flow_id=pid, status=2, started_at=now,
                          finished_at=now, in_num=rows, out_num=rows,
                          err_num=0))
        # pipeline job in project 8201
        s.query(PipelineNodeRun).filter_by(asset_id=8211).delete()
        s.query(Job).filter_by(asset_id=8211).delete()
        s.query(Asset).filter_by(id=8211).delete()
        s.add(Asset(id=8211, project_id=8201, type="pipeline",
                    key="pipeline_dash_8211", name="中文管道",
                    owner="tester", enabled=True))
        s.flush()
        job = Job(asset_id=8211, asset_type="pipeline", status="success",
                  created_at=now, finished_at=now, attempts=1)
        s.add(job)
        s.flush()
        s.add(PipelineNodeRun(job_id=job.id, asset_id=8211, node_id="src",
                              status="success", in_num=0, out_num=5,
                              ms=10))
        s.add(PipelineNodeRun(job_id=job.id, asset_id=8211, node_id="sink",
                              status="success", in_num=5, out_num=5,
                              ms=10))
        s.commit()


def _h(uid, project):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_dashboard_counts_are_project_scoped():
    _seed()
    c = TestClient(app)
    other = c.get("/api/v1/dashboard", headers=_h(8202, 8202)).json()
    assert other["datasources"] == 1
    assert other["flows"] == 1
    assert other["interfaces"] == 1
    assert other["quality_rules"] == 1
    assert other["open_alerts"] == 1

    own = c.get("/api/v1/dashboard", headers=_h(8201, 8201)).json()
    assert own["datasources"] == 1
    assert own["flows"] == 1
    assert own["quality_rules"] == 1
    assert own["open_alerts"] == 1
    assert own["runs_24h"] == 2


def test_dashboard_recent_runs_include_pipeline_and_stay_scoped():
    _seed()
    c = TestClient(app)
    own = c.get("/api/v1/dashboard", headers=_h(8201, 8201)).json()
    names = [r["flow"] for r in own["recent_runs"]]
    assert "中文管道" in names
    assert "flow_8201" in names
    pipe = next(r for r in own["recent_runs"] if r["flow"] == "中文管道")
    assert pipe["status"] == 2
    assert pipe["in"] == 5 and pipe["out"] == 5
    assert pipe["asset_id"] == 8211

    other = c.get("/api/v1/dashboard", headers=_h(8202, 8202)).json()
    names = [r["flow"] for r in other["recent_runs"]]
    assert "中文管道" not in names
    assert "flow_8201" not in names
    assert "flow_8202" in names
