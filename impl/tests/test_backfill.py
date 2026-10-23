from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import pytest

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import AssetVersion, Datasource, Job, Project
from odf.pipeline.runner import execute_backfill
from odf.services.crypto import encrypt_secret
from odf.services.jobs import enqueue_asset, process_job


def _env(tmp_path):
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="b1", name="b1", status=1))
    src_url = "sqlite:///" + str(tmp_path / "src.db")
    dst_url = "sqlite:///" + str(tmp_path / "dst.db")
    raw = create_engine(src_url)
    with raw.begin() as c:
        c.execute(text("create table events (id int primary key, v text)"))
        c.execute(text("insert into events values "
                       "(1,'a'),(2,'b'),(3,'c'),(4,'d'),(5,'e')"))
    raw2 = create_engine(dst_url)
    with raw2.begin() as c:
        c.execute(text("create table dest (id int primary key, v text)"))
    s.add_all([
        Datasource(id=1, project_id=1, name="src", kind="sqlite",
                   dsn_encrypted=encrypt_secret(src_url)),
        Datasource(id=2, project_id=1, name="dst", kind="sqlite",
                   dsn_encrypted=encrypt_secret(dst_url)),
    ])
    s.commit()
    content = {
        "nodes": [
            {"id": "s", "type": "source",
             "config": {"datasource_id": 1, "table": "events", "pk": "id",
                        "cursor_column": "id"}},
            {"id": "k", "type": "sink",
             "config": {"datasource_id": 2, "table": "dest", "pk": ["id"],
                        "mode": "append"}},
        ],
        "edges": [{"from": "s", "to": "k"}],
        "settings": {"batch": 2},
    }
    a = create_asset(s, 1, "pipeline", "P", content, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    a.cursor_json = {"s": "[1,1]"}
    s.commit()
    return s, a, dst_url


def _dest(url):
    e = create_engine(url)
    with e.connect() as c:
        return [dict(r) for r in c.execute(
            text("select id, v from dest order by id")).mappings()]


def test_backfill_replays_until_exhausted(tmp_path):
    s, asset, dst = _env(tmp_path)
    out = execute_backfill(s, asset.id, "1", max_batches=10)
    assert out["rows_in"] == 4 and out["rows_out"] == 4
    assert out["batches"] == 3
    assert out["exhausted"] is True
    assert [r["id"] for r in _dest(dst)] == [2, 3, 4, 5]
    s.refresh(asset)
    assert asset.cursor_json == {"s": "[1,1]"}


def test_backfill_stops_at_end_cursor(tmp_path):
    s, asset, dst = _env(tmp_path)
    out = execute_backfill(s, asset.id, "1", end_cursor="3", max_batches=10)
    assert out["rows_in"] == 2 and out["rows_out"] == 2
    assert [r["id"] for r in _dest(dst)] == [2, 3]
    assert out["exhausted"] is True


def test_backfill_end_cursor_is_numeric_not_lexical(tmp_path):
    s, asset, dst = _env(tmp_path)
    out = execute_backfill(s, asset.id, "1", end_cursor="10",
                           max_batches=10)
    assert out["rows_in"] == 4
    assert [r["id"] for r in _dest(dst)] == [2, 3, 4, 5]


def test_backfill_date_boundary_covers_the_day():
    from odf.pipeline.nodes.source import _within

    assert _within(datetime(2026, 1, 1, 15, 30), "2026-01-01") is True
    assert _within(datetime(2026, 1, 2, 0, 0), "2026-01-01") is False
    assert _within("9", "10") is True
    assert _within("2026-01-01T10:00:00", "2026-01-01T09:00:00") is False


def test_backfill_respects_max_batches(tmp_path):
    s, asset, dst = _env(tmp_path)
    out = execute_backfill(s, asset.id, "1", max_batches=1)
    assert out["rows_in"] == 2
    assert out["batches"] == 1
    assert out["exhausted"] is False
    assert [r["id"] for r in _dest(dst)] == [2, 3]


def test_backfill_job_wiring(tmp_path):
    s, asset, dst = _env(tmp_path)
    job = Job(asset_id=asset.id, asset_type="pipeline_backfill",
              status="running", payload_json={"start_cursor": "1",
                                              "max_batches": 2})
    s.add(job)
    s.commit()
    process_job(s, job, "w")
    s.refresh(job)
    assert job.status == "success"
    assert [r["id"] for r in _dest(dst)] == [2, 3, 4, 5]


def test_backfill_sink_failure_does_not_advance(tmp_path):
    s, asset, dst = _env(tmp_path)
    raw = create_engine(dst)
    with raw.begin() as c:
        c.execute(text("drop table dest"))
        c.execute(text("create table dest (id int primary key, v text, "
                       "must text not null)"))
    v = s.get(AssetVersion, asset.published_version_id)
    content = {**v.content_json,
               "nodes": [dict(n) for n in v.content_json["nodes"]]}
    content["nodes"][1]["on_error"] = "skip"
    v.content_json = content
    s.commit()
    with pytest.raises(ValueError):
        execute_backfill(s, asset.id, "1", max_batches=10)
    assert _dest(dst) == []
    s.refresh(asset)
    assert asset.cursor_json == {"s": "[1,1]"}


def test_backfill_job_resumes_from_last_batch(tmp_path):
    s, asset, dst = _env(tmp_path)
    job = Job(asset_id=asset.id, asset_type="pipeline_backfill",
              status="running", payload_json={"start_cursor": "1",
                                              "max_batches": 10})
    s.add(job)
    s.commit()
    execute_backfill(s, asset.id, "1", max_batches=1, job_id=job.id)
    s.refresh(job)
    assert job.payload_json["last_result"]["exhausted"] is False
    assert job.payload_json["last_result"]["rows_in"] == 2
    resume = job.payload_json["resume_cursors"]
    assert resume["s"] != "[1,1]"
    out = execute_backfill(s, asset.id, "1", max_batches=10,
                           resume_cursors=resume)
    assert out["exhausted"] is True
    assert [r["id"] for r in _dest(dst)] == [2, 3, 4, 5]


def test_backfill_enqueue_rejects_conflicting_payload(tmp_path):
    s, asset, _ = _env(tmp_path)
    j = enqueue_asset(s, asset.id, "pipeline_backfill",
                      {"start_cursor": "1", "max_batches": 10})
    assert enqueue_asset(s, asset.id, "pipeline_backfill",
                         {"start_cursor": "1", "max_batches": 10}).id == j.id
    with pytest.raises(ValueError):
        enqueue_asset(s, asset.id, "pipeline_backfill",
                      {"start_cursor": "4", "max_batches": 10})


def test_backfill_requires_cursor_column(tmp_path):
    s, asset, _ = _env(tmp_path)
    v = s.get(AssetVersion, asset.published_version_id)
    content = dict(v.content_json)
    content["nodes"] = [dict(n) for n in v.content_json["nodes"]]
    content["nodes"][0]["config"] = {
        k: v for k, v in content["nodes"][0]["config"].items()
        if k != "cursor_column"}
    v.content_json = content
    s.commit()
    with pytest.raises(ValueError):
        execute_backfill(s, asset.id, "1")


def test_backfill_route_enqueues(tmp_path):
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import User
    from odf.services.auth import create_token

    src_url = "sqlite:///" + str(tmp_path / "rsrc.db")
    dst_url = "sqlite:///" + str(tmp_path / "rdst.db")
    with create_engine(src_url).begin() as c:
        c.execute(text("create table e (id int primary key, v text)"))
    with create_engine(dst_url).begin() as c:
        c.execute(text("create table d (id int primary key, v text)"))
    with SessionLocal() as s:
        for did, name, url in ((801, "rs", src_url), (802, "rd", dst_url)):
            ds = s.get(Datasource, did)
            if ds:
                ds.dsn_encrypted = encrypt_secret(url)
                ds.project_id = 1
            else:
                s.add(Datasource(id=did, project_id=1, name=name,
                                 kind="sqlite",
                                 dsn_encrypted=encrypt_secret(url)))
        content = {
            "nodes": [
                {"id": "s", "type": "source",
                 "config": {"datasource_id": 801, "table": "e", "pk": "id",
                            "cursor_column": "id"}},
                {"id": "k", "type": "sink",
                 "config": {"datasource_id": 802, "table": "d",
                            "pk": ["id"], "mode": "append"}},
            ],
            "edges": [{"from": "s", "to": "k"}],
            "settings": {"batch": 100},
        }
        a = create_asset(s, 1, "pipeline", "RB", content, "admin",
                         enabled=False)
        publish_asset(s, a.id, "admin")
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="bk", password_hash="x", role="admin",
                     active=True)
            s.add(u)
        u.role, u.active = "admin", True
        s.commit()
        aid = a.id
    c = TestClient(app)
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    r = c.post(f"/api/v1/pipelines/{aid}/backfill",
               json={"start_cursor": "0", "max_batches": 1}, headers=h)
    assert r.status_code == 200 and r.json()["job_id"]
    assert c.get(f"/api/v1/pipelines/{aid}/cursors",
                 headers=h).json()["sources"][0]["node_id"] == "s"
    r = c.put(f"/api/v1/pipelines/{aid}/cursors",
              json={"node_id": "s", "cursor": "5"}, headers=h)
    assert r.status_code == 200 and r.json()["cursors"]["s"] == "5"
    assert c.post(f"/api/v1/pipelines/{aid}/backfill",
                  json={"start_cursor": " "}, headers=h).status_code == 400
    with SessionLocal() as s:
        a = s.get(type(a), aid)
        v = s.get(AssetVersion, a.published_version_id)
        content = {**v.content_json,
                   "nodes": [dict(n) for n in v.content_json["nodes"]]}
        content["nodes"][0]["config"] = {
            k: val for k, val in content["nodes"][0]["config"].items()
            if k != "cursor_column"}
        v.content_json = content
        s.commit()
    r = c.post(f"/api/v1/pipelines/{aid}/backfill",
               json={"start_cursor": "0"}, headers=h)
    assert r.status_code == 400
    assert "cursor column" in r.json()["detail"]
