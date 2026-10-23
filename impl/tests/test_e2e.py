import base64
import hashlib
import hmac
import os
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import AkSk
from odf.services.crypto import encrypt_secret
from odf.services.datasource import create_datasource
from odf.services.flow import create_flow
from odf.services.interface import (create_interface, execute_interface,
                                    publish_interface)
from odf.services.metadata import sync_datasource
from odf.settings import get_settings
from odf.workers.etl import run_flow

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
        c.execute(text("drop table if exists e2e_src"))
        c.execute(text("drop table if exists e2e_dst"))
        c.execute(text("drop table if exists e2e_tie"))
        c.execute(text("drop table if exists e2e_tie_dst"))
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


def test_closed_loop(seed):
    with SessionLocal() as session:
        src = create_datasource(session, 1, "src", seed, "sqlite")
        dst = create_datasource(session, 1, "dst", seed, "sqlite")
        assert sync_datasource(session, src.id) >= 2

        flow = create_flow(session, 1, "copy", "0 */5 * * * ?", {
            "source_ds_id": src.id, "sink_ds_id": dst.id,
            "source_table": "e2e_src", "sink_table": "e2e_dst",
            "pk": "id", "cursor_column": "id", "batch": 100})
        run = run_flow(session, flow.id)
        assert run.status == 2 and run.out_num == 10

        run2 = run_flow(session, flow.id)
        assert run2.in_num == 0

        iface = create_interface(session, 1, dst.id, "count",
                                 "select count(*) as n from e2e_dst", [])
        publish_interface(session, iface.id)
        rows, total = execute_interface(session, iface.id, {})
        assert total == 1 and rows[0]["n"] == 10

        session.add(AkSk(project_id=1, ak="ak1",
                         sk_encrypted=encrypt_secret("sk1")))
        session.commit()
        path = "/openapi/%s" % iface.interface_key
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
        flow = create_flow(session, 1, "copy2", "0 */5 * * * ?", {
            "source_ds_id": src.id, "sink_ds_id": dst.id,
            "source_table": "e2e_src", "sink_table": "e2e_dst",
            "pk": "id", "cursor_column": "id", "batch": 100})
        run1 = run_flow(session, flow.id)
        assert run1.status == 2
        with create_engine(seed).begin() as c:
            c.execute(text("drop table e2e_dst"))
        run2 = run_flow(session, flow.id)
        assert run2.status == 3
        assert run2.cursor_value == run1.cursor_value


def test_tie_rows_are_not_lost(seed):
    with SessionLocal() as session:
        src = create_datasource(session, 1, "src3", seed, "sqlite")
        dst = create_datasource(session, 1, "dst3", seed, "sqlite")
        flow = create_flow(session, 1, "copy3", "0 */5 * * * ?", {
            "source_ds_id": src.id, "sink_ds_id": dst.id,
            "source_table": "e2e_tie", "sink_table": "e2e_tie_dst",
            "pk": "id", "cursor_column": "ts", "batch": 1})
        r1 = run_flow(session, flow.id)
        r2 = run_flow(session, flow.id)
        r3 = run_flow(session, flow.id)
        assert r1.out_num == 1
        assert r2.out_num == 1
        assert r3.in_num == 0
