import base64
import hashlib
import hmac
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from odf.assets.service import create_asset, publish_asset
from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import AkSk
from odf.pipeline.runner import PipelineRunError, execute_pipeline
from odf.services.crypto import encrypt_secret
from odf.services.datasource import create_datasource
from odf.services.metadata import sync_datasource
from odf.settings import get_settings

pytestmark = pytest.mark.integration


@pytest.fixture()
def seed():
    url = os.environ.get("ODF_TEST_DATABASE_URL")
    if not url:
        pytest.skip("ODF_TEST_DATABASE_URL not set")
    if "test" not in url:
        pytest.skip("ODF_TEST_DATABASE_URL must look like a test database")
    if get_settings().database_url != url:
        pytest.skip("ODF_DATABASE_URL must equal ODF_TEST_DATABASE_URL")
    e = create_engine(url)
    Base.metadata.drop_all(e)
    Base.metadata.create_all(e)
    with e.begin() as c:
        c.execute(text("insert into project (id, code, name, status, created_at) "
                       "values (1, 'p', 'p', 1, CURRENT_TIMESTAMP)"))
        for name in ("e2e_src", "e2e_dst", "e2e_tie", "e2e_tie_dst"):
            c.execute(text("drop table if exists %s" % name))
        c.execute(text("create table e2e_src (id int primary key, v text)"))
        c.execute(text("create table e2e_dst (id int primary key, v text)"))
        c.execute(text("create table e2e_tie (id int primary key, ts text)"))
        c.execute(text("create table e2e_tie_dst (id int primary key, ts text)"))
        for i in range(1, 11):
            c.execute(text("insert into e2e_src values (:i, :v)"),
                      {"i": i, "v": "v%d" % i})
        c.execute(text("insert into e2e_tie values (1, 't')"))
        c.execute(text("insert into e2e_tie values (2, 't')"))
    yield url
    e.dispose()


def _signed_headers(ak, sk, method, path, body):
    date = str(int(time.time() * 1000))
    md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
    s2s = "\n".join([method, md5, "application/json", date, path])
    sig = base64.b64encode(
        hmac.new(sk.encode(), s2s.encode(), hashlib.sha1).digest()).decode()
    return {"Authorization": "%s:%s" % (ak, sig),
            "projectKey": "p", "Content-Type": "application/json", "Date": date}


def _pipeline(session, name, src_id, dst_id, src_table, dst_table,
              cursor="id", batch=100):
    content = {"nodes": [
        {"id": "source_1", "type": "source",
         "config": {"datasource_id": src_id, "table": src_table,
                    "cursor_column": cursor, "pk": "id"}},
        {"id": "sink_1", "type": "sink",
         "config": {"datasource_id": dst_id, "table": dst_table,
                    "mode": "upsert", "pk": ["id"]}}],
        "edges": [{"from": "source_1", "to": "sink_1"}],
        "settings": {"batch": batch}}
    asset = create_asset(session, 1, "pipeline", name, content, "admin")
    publish_asset(session, asset.id, "admin")
    return asset


def test_closed_loop(seed):
    with SessionLocal() as session:
        src = create_datasource(session, 1, "src", seed, "sqlite")
        dst = create_datasource(session, 1, "dst", seed, "sqlite")
        assert sync_datasource(session, src.id) >= 2

        pipeline = _pipeline(session, "copy", src.id, dst.id,
                             "e2e_src", "e2e_dst")
        first = execute_pipeline(session, pipeline.id)
        assert first["source_rows"] == 10
        second = execute_pipeline(session, pipeline.id)
        assert second["source_rows"] == 0

        api = create_asset(session, 1, "api", "count", {
            "mode": "sql", "query": {"datasource_id": dst.id},
            "sql": "select count(*) as n from e2e_dst", "params": [],
            "auth": {"type": "aksk"}}, "admin")
        publish_asset(session, api.id, "admin")

        session.add(AkSk(project_id=1, ak="ak1",
                         sk_encrypted=encrypt_secret("sk1")))
        session.commit()
        path = "/openapi/%s" % api.key
        body = b"{}"
        r = TestClient(app).post(path, content=body,
                                 headers=_signed_headers("ak1", "sk1", "POST",
                                                         path, body))
        assert r.status_code == 200
        assert r.json()["results"][0]["n"] == 10


def test_failure_does_not_advance_cursor(seed):
    with SessionLocal() as session:
        src = create_datasource(session, 1, "src2", seed, "sqlite")
        dst = create_datasource(session, 1, "dst2", seed, "sqlite")
        pipeline = _pipeline(session, "copy2", src.id, dst.id,
                             "e2e_src", "e2e_dst")
        execute_pipeline(session, pipeline.id)
        cursor = dict(pipeline.cursor_json or {})
        with create_engine(seed).begin() as c:
            c.execute(text("drop table e2e_dst"))
        with pytest.raises(PipelineRunError):
            execute_pipeline(session, pipeline.id)
        session.refresh(pipeline)
        assert dict(pipeline.cursor_json or {}) == cursor


def test_tie_rows_are_not_lost(seed):
    with SessionLocal() as session:
        src = create_datasource(session, 1, "src3", seed, "sqlite")
        dst = create_datasource(session, 1, "dst3", seed, "sqlite")
        pipeline = _pipeline(session, "copy3", src.id, dst.id,
                             "e2e_tie", "e2e_tie_dst", cursor="ts", batch=1)
        r1 = execute_pipeline(session, pipeline.id)
        r2 = execute_pipeline(session, pipeline.id)
        r3 = execute_pipeline(session, pipeline.id)
        assert r1["source_rows"] == 1
        assert r2["source_rows"] == 1
        assert r3["source_rows"] == 0
