import uuid
from datetime import datetime, timedelta, timezone

import pytest

from odf.db import SessionLocal
from odf.models import Asset, AssetVersion, Job, Project
from odf.services.dependencies import (add_dependency, delete_dependency,
                                       dependencies_satisfied,
                                       list_dependencies)
from odf.services.jobs import scheduler_tick

PROJECT_ID = 918


def _project():
    with SessionLocal() as s:
        if not s.get(Project, PROJECT_ID):
            s.add(Project(id=PROJECT_ID, code="deps", name="Deps", status=1))
            s.commit()


def _pipeline(s, name):
    row = Asset(project_id=PROJECT_ID, type="pipeline",
                key=uuid.uuid4().hex, name=name, owner="tester",
                cron="0 * * * * ?", enabled=True)
    s.add(row)
    s.flush()
    version = AssetVersion(asset_id=row.id, version=1,
                           content_json={"nodes": [], "edges": []},
                           status="published", created_by="tester")
    s.add(version)
    s.flush()
    row.draft_version_id = version.id
    row.published_version_id = version.id
    s.commit()
    return row


def test_dependency_edges_validate_and_round_trip():
    _project()
    with SessionLocal() as s:
        a = _pipeline(s, "dep-a")
        b = _pipeline(s, "dep-b")
        c = _pipeline(s, "dep-c")
        edge = add_dependency(s, PROJECT_ID, "pipeline", b.id, "pipeline",
                              a.id)
        assert edge.id
        assert add_dependency(s, PROJECT_ID, "pipeline", b.id,
                              "pipeline", a.id).id == edge.id
        with pytest.raises(ValueError):
            add_dependency(s, PROJECT_ID, "pipeline", a.id, "pipeline", a.id)
        add_dependency(s, PROJECT_ID, "pipeline", c.id, "pipeline", b.id)
        with pytest.raises(ValueError):
            add_dependency(s, PROJECT_ID, "pipeline", a.id, "pipeline", c.id)
        rows = list_dependencies(s, PROJECT_ID)
        assert {r["upstream_name"] for r in rows} >= {"dep-a", "dep-b"}
        delete_dependency(s, PROJECT_ID, edge.id)
        assert all(r["id"] != edge.id for r in list_dependencies(s, PROJECT_ID))


def test_dependency_requires_recent_success():
    _project()
    with SessionLocal() as s:
        a = _pipeline(s, "up-a")
        b = _pipeline(s, "down-b")
        add_dependency(s, PROJECT_ID, "pipeline", b.id, "pipeline", a.id)
        now = datetime.now(timezone.utc)
        assert not dependencies_satisfied(s, PROJECT_ID, "pipeline", b.id,
                                          now=now)["satisfied"]
        s.add(Job(asset_id=a.id, asset_type="pipeline", status="failed",
                  run_at=now, finished_at=now))
        s.commit()
        assert not dependencies_satisfied(s, PROJECT_ID, "pipeline", b.id,
                                          now=now)["satisfied"]
        s.add(Job(asset_id=a.id, asset_type="pipeline", status="success",
                  run_at=now, finished_at=now))
        s.commit()
        assert dependencies_satisfied(s, PROJECT_ID, "pipeline", b.id,
                                      now=now)["satisfied"]
        later = now + timedelta(hours=30)
        assert not dependencies_satisfied(s, PROJECT_ID, "pipeline", b.id,
                                          now=later)["satisfied"]


def test_scheduler_skips_blocked_pipeline_and_runs_after_success():
    _project()
    with SessionLocal() as s:
        upstream = _pipeline(s, "sched-up")
        downstream = _pipeline(s, "sched-down")
        add_dependency(s, PROJECT_ID, "pipeline", downstream.id,
                       "pipeline", upstream.id)
        now = datetime.now(timezone.utc)
        scheduler_tick(s, now=now)
        skipped = (s.query(Job).filter_by(asset_id=downstream.id)
                   .order_by(Job.id.desc()).first())
        assert skipped and skipped.status == "skipped"
        assert "waiting for upstream" in (skipped.last_error or "")
        assert "sched-up" in (skipped.last_error or "")

        s.add(Job(asset_id=upstream.id, asset_type="pipeline",
                  status="success", run_at=now, finished_at=now))
        s.commit()
        scheduler_tick(s, now=now + timedelta(hours=1, minutes=1))
        queued = (s.query(Job).filter_by(asset_id=downstream.id,
                                         status="queued").first())
        assert queued is not None


def test_dependency_routes_validate_and_delete():
    from fastapi.testclient import TestClient

    from odf.main import app
    from odf.models import User
    from odf.services.auth import create_token

    _project()
    with SessionLocal() as s:
        if not s.get(User, 9911):
            s.add(User(id=9911, username="dep-editor", password_hash="x",
                       role="editor", active=True))
            s.commit()
        a = _pipeline(s, "api-up")
        b = _pipeline(s, "api-down")
        ids = (a.id, b.id)
    client = TestClient(app)
    headers = {"Authorization": "Bearer " + create_token(9911, PROJECT_ID)}
    body = {"downstream_type": "pipeline", "downstream_id": ids[1],
            "upstream_type": "pipeline", "upstream_id": ids[0]}
    created = client.post("/api/v1/dependencies", json=body, headers=headers)
    assert created.status_code == 201
    dep_id = created.json()["id"]
    rows = client.get("/api/v1/dependencies", headers=headers).json()
    assert any(r["id"] == dep_id and r["upstream_name"] == "api-up"
               for r in rows)
    cycle = client.post("/api/v1/dependencies", json={
        "downstream_type": "pipeline", "downstream_id": ids[0],
        "upstream_type": "pipeline", "upstream_id": ids[1]},
        headers=headers)
    assert cycle.status_code == 400
    assert client.delete(f"/api/v1/dependencies/{dep_id}",
                         headers=headers).status_code == 204


def test_recent_blocked_lists_skipped_dependencies():
    from odf.services.dependencies import recent_blocked

    _project()
    with SessionLocal() as s:
        up = _pipeline(s, "blocked-up")
        down = _pipeline(s, "blocked-down")
        add_dependency(s, PROJECT_ID, "pipeline", down.id, "pipeline", up.id)
        scheduler_tick(s, now=datetime.now(timezone.utc))
        rows = recent_blocked(s, PROJECT_ID, hours=1)
        assert any(r["name"] == "blocked-down"
                   and "blocked-up" in r["reason"] for r in rows)
        assert recent_blocked(s, 9999, hours=1) == []
