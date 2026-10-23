import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from odf import clickhouse
from odf.models import Datasource
from odf.services.crypto import encrypt_secret
from odf.services.datasource import get_dsn
from odf.services.metadata import list_tables, sync_datasource
from odf.workbench.service import run_query


def env(name: str) -> str:
    import os
    value = os.environ.get(name)
    if not value:
        pytest.skip("%s is not configured" % name)
    return value


def has_env(name: str) -> bool:
    import os
    return bool(os.environ.get(name))

pytestmark = pytest.mark.integration


def _ds(session, kind, url, did=1):
    ds = Datasource(id=did, project_id=1, name=kind, kind=kind,
                    dsn_encrypted=encrypt_secret(url))
    session.add(ds)
    session.commit()
    return ds


def test_postgres_live(control):
    url = env("ODF_IT_POSTGRES_URL")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("drop table if exists it_events"))
        c.execute(text("create table it_events (id int primary key, name text)"))
        c.execute(text("insert into it_events values (1,'a'),(2,'b')"))
    try:
        ds = _ds(control, "postgres", url)
        assert sync_datasource(control, ds.id) >= 1
        names = {(t["schema"], t["table"]) for t in list_tables(control, ds.id)}
        assert ("public", "it_events") in names
        out = run_query(control, 1, ds.id,
                        "select id, name from it_events order by id")
        assert out["rows"] == [{"id": 1, "name": "a"},
                               {"id": 2, "name": "b"}]
    finally:
        with raw.begin() as c:
            c.execute(text("drop table if exists it_events"))
        raw.dispose()


def test_clickhouse_live(control):
    url = env("ODF_IT_CLICKHOUSE_URL")
    opts = clickhouse.parse_dsn(url)
    import clickhouse_connect
    client = clickhouse_connect.get_client(
        host=opts["host"], port=opts["port"], username=opts["username"],
        password=opts["password"], database=opts["database"],
        secure=opts["secure"])
    try:
        client.command("drop table if exists it_events")
        client.command("create table it_events (id UInt64, name String) "
                       "engine=MergeTree order by id")
        client.insert("it_events", [(1, "a"), (2, "b")],
                      column_names=["id", "name"])
        ds = _ds(control, "clickhouse", url)
        assert sync_datasource(control, ds.id) >= 1
        names = {(t["schema"], t["table"]) for t in list_tables(control, ds.id)}
        assert (opts["database"], "it_events") in names
        out = clickhouse.execute(
            ds, "select id, name from it_events order by id", {}, 10)
        assert out["rows"] == [{"id": 1, "name": "a"},
                               {"id": 2, "name": "b"}]
    finally:
        client.command("drop table if exists it_events")
        client.close()


def test_mssql_live(control):
    url = env("ODF_IT_MSSQL_URL")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("if object_id('dbo.it_events') is not null "
                       "drop table dbo.it_events"))
        c.execute(text("create table dbo.it_events (id int primary key, "
                       "name nvarchar(100))"))
        c.execute(text("insert into dbo.it_events values (1,'a'),(2,'b')"))
    try:
        ds = _ds(control, "mssql", url)
        assert sync_datasource(control, ds.id) >= 1
        names = {(t["schema"], t["table"]) for t in list_tables(control, ds.id)}
        assert ("dbo", "it_events") in names
        out = run_query(control, 1, ds.id,
                        "select id, name from dbo.it_events order by id")
        assert [r["name"] for r in out["rows"]] == ["a", "b"]
    finally:
        with raw.begin() as c:
            c.execute(text("if object_id('dbo.it_events') is not null "
                           "drop table dbo.it_events"))
        raw.dispose()


def test_oracle_live(control):
    url = env("ODF_IT_ORACLE_URL")
    raw = create_engine(url)
    with raw.begin() as c:
        try:
            c.execute(text("drop table it_events purge"))
        except Exception:
            pass
        c.execute(text("create table it_events (id number primary key, "
                       "name varchar2(100))"))
        c.execute(text("insert into it_events values (1,'a')"))
        c.execute(text("insert into it_events values (2,'b')"))
    try:
        ds = _ds(control, "oracle", url)
        assert sync_datasource(control, ds.id) >= 1
        tables = {t["table"].upper() for t in list_tables(control, ds.id)}
        assert "IT_EVENTS" in tables
        out = run_query(control, 1, ds.id,
                        "select id, name from it_events order by id")
        assert [r["name"] for r in out["rows"]] == ["a", "b"]
    finally:
        with raw.begin() as c:
            try:
                c.execute(text("drop table it_events purge"))
            except Exception:
                pass
        raw.dispose()


def test_s3_live(tmp_path):
    if not has_env("ODF_IT_S3_ENDPOINT"):
        pytest.skip("ODF_IT_S3_ENDPOINT is not configured")
    import boto3
    from odf.files.storage import S3Storage
    endpoint = env("ODF_IT_S3_ENDPOINT")
    bucket = env("ODF_IT_S3_BUCKET")
    settings = SimpleNamespace(
        s3_endpoint=endpoint, s3_bucket=bucket,
        s3_access_key=env("ODF_IT_S3_ACCESS_KEY"),
        s3_secret_key=env("ODF_IT_S3_SECRET_KEY"),
        s3_region="us-east-1")
    client = boto3.client(
        "s3", endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name="us-east-1")
    try:
        client.create_bucket(Bucket=bucket)
    except client.exceptions.BucketAlreadyOwnedByYou:
        pass
    src = tmp_path / "payload.bin"
    src.write_bytes(b"odf-integration")
    storage = S3Storage(settings)
    storage.put("it/payload.bin", src)
    assert storage.exists("it/payload.bin")
    assert b"".join(storage.open("it/payload.bin")) == b"odf-integration"
    storage.delete("it/payload.bin")
    assert not storage.exists("it/payload.bin")


def test_oidc_discovery_live(monkeypatch):
    if not has_env("ODF_IT_OIDC_ISSUER"):
        pytest.skip("ODF_IT_OIDC_ISSUER is not configured")
    from odf.services import oidc
    issuer = env("ODF_IT_OIDC_ISSUER").rstrip("/")
    settings = SimpleNamespace(
        oidc_issuer=issuer,
        oidc_client_id=env("ODF_IT_OIDC_CLIENT_ID"),
        oidc_client_secret=env("ODF_IT_OIDC_CLIENT_SECRET"),
        oidc_redirect_uri="http://localhost:18081/api/v1/auth/oidc/callback",
        oidc_scopes="openid profile email", oidc_auto_provision=True,
        jwt_secret="integration-state-secret")
    monkeypatch.setattr(oidc, "get_settings", lambda: settings)
    url, state, nonce = oidc.start_flow(1)
    assert issuer + "/protocol/openid-connect/auth" in url
    assert "code_challenge_method=S256" in url
    assert oidc._decode_state(state)["nonce"] == nonce


def test_ldap_live(monkeypatch):
    if not has_env("ODF_IT_LDAP_URL"):
        pytest.skip("ODF_IT_LDAP_URL is not configured")
    pytest.importorskip("ldap3")
    from odf.services import ldap_auth
    settings = SimpleNamespace(
        ldap_url=env("ODF_IT_LDAP_URL"),
        ldap_user_dn_template=env("ODF_IT_LDAP_USER_DN_TEMPLATE"))
    monkeypatch.setattr(ldap_auth, "get_settings", lambda: settings)
    assert ldap_auth.authenticate_ldap(
        "alice", env("ODF_IT_LDAP_PASSWORD")) == "alice"


def test_postgres_scheduler_advisory_lock():
    url = env("ODF_IT_POSTGRES_URL")
    engine = create_engine(url)
    c1 = engine.connect()
    c2 = engine.connect()
    try:
        assert c1.execute(text("select pg_try_advisory_lock(999999)")).scalar()
        assert not c2.execute(
            text("select pg_try_advisory_lock(999999)")).scalar()
        c1.execute(text("select pg_advisory_unlock(999999)"))
        assert c2.execute(text("select pg_try_advisory_lock(999999)")).scalar()
        c2.execute(text("select pg_advisory_unlock(999999)"))
    finally:
        c1.close()
        c2.close()
        engine.dispose()
