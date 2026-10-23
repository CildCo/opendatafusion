import base64
import hashlib
import hmac
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import AkSk, ApiRate, ApiCallStat, Datasource, Project
from odf.services.aksk import sign, string_to_sign
from odf.services.crypto import encrypt_secret
from odf.services.ratelimit import check_rate, client_allowed, record_stat


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="r1", name="r1", status=1))
    s.commit()
    return s


def test_ip_allowlist():
    assert client_allowed("127.0.0.1", [])
    assert client_allowed("192.0.2.3", ["192.0.2.0/24"])
    assert not client_allowed("198.51.100.3", ["192.0.2.0/24"])
    assert client_allowed("2001:db8::1", ["2001:db8::/32"])


def test_rate_limit_window():
    s = _env()
    now = datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc)
    assert check_rate(s, "k", 2, now)
    assert check_rate(s, "k", 2, now)
    assert not check_rate(s, "k", 2, now)
    later = datetime(2026, 10, 21, 12, 1, tzinfo=timezone.utc)
    assert check_rate(s, "k", 2, later)


def test_record_and_aggregate_stats():
    s = _env()
    day = datetime(2026, 10, 21).date()
    record_stat(s, day, 1, "ak", True, 10)
    record_stat(s, day, 1, "ak", False, 20)
    row = s.query(ApiCallStat).first()
    assert row.count == 2 and row.errors == 1 and row.total_ms == 30
    assert s.query(ApiRate).count() == 0


def _gateway_env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "gov.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
        c.execute(text("insert into t values (1)"))
    with SessionLocal() as s:
        for pid, code in ((961, "gov961"),):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        row = s.get(Datasource, 961)
        if row:
            row.dsn_encrypted = encrypt_secret(url)
            row.project_id = 961
        else:
            s.add(Datasource(id=961, project_id=961, name="gov",
                             kind="sqlite",
                             dsn_encrypted=encrypt_secret(url)))
        s.commit()
        content = {"mode": "visual",
                   "query": {"datasource_id": 961, "table": "t",
                             "select": [{"column": "id"}]},
                   "params": [], "sql": None,
                   "auth": {"type": "aksk", "rate_limit_per_min": 1,
                            "ip_allowlist": ["127.0.0.1"]}}
        a = create_asset(s, 961, "api", "Governed", content, "admin",
                         enabled=False)
        publish_asset(s, a.id, "admin")
        keyrow = s.query(AkSk).filter_by(ak="govak").first()
        if keyrow:
            keyrow.project_id = 961
            keyrow.sk_encrypted = encrypt_secret("govsk")
            keyrow.enabled = True
            keyrow.ip_allowlist = ["127.0.0.1"]
            keyrow.rate_limit_per_min = 10
        else:
            s.add(AkSk(project_id=961, ak="govak",
                       sk_encrypted=encrypt_secret("govsk"), enabled=True,
                       ip_allowlist=["127.0.0.1"], rate_limit_per_min=10))
        s.query(ApiRate).delete()
        s.commit()
        return a.key


def _call(key, ak="govak", sk="govsk", project="gov961"):
    path = "/openapi/%s" % key
    body = b"{}"
    date = str(int(time.time() * 1000))
    ctype = "application/json"
    s2s = string_to_sign("POST", body, ctype, date, path)
    auth = ak + ":" + sign(sk, s2s)
    return TestClient(app).post(path, content=body, headers={
        "projectKey": project, "Authorization": auth, "Date": date,
        "Content-Type": ctype})


def test_gateway_ip_rate_and_stats(tmp_path):
    from odf.models import User
    from odf.services.auth import create_token
    key = _gateway_env(tmp_path)
    assert _call(key).status_code == 200
    assert _call(key).status_code == 429
    with SessionLocal() as s:
        ak = s.query(AkSk).filter_by(ak="govak").first()
        ak.ip_allowlist = ["192.0.2.1"]
        s.query(ApiRate).delete()
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="gov", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        else:
            u.role = "admin"
            u.active = True
        s.commit()
    assert _call(key).status_code == 403
    with SessionLocal() as s:
        tok = create_token(1, 961)
    r = TestClient(app).get("/api/v1/api-stats", headers={
        "Authorization": "Bearer " + tok})
    assert r.status_code == 200
    assert r.json()[0]["count"] >= 2
    with SessionLocal() as s:
        u = s.get(User, 1)
        u.role = "viewer"
        s.commit()
    assert TestClient(app).get("/api/v1/api-stats", headers={
        "Authorization": "Bearer " + tok}).status_code == 403
    with SessionLocal() as s:
        u = s.get(User, 1)
        u.role = "admin"
        s.commit()


def test_aksk_policy_route(tmp_path):
    from odf.models import User
    from odf.services.auth import create_token
    _gateway_env(tmp_path)
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="gov", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        else:
            u.role = "admin"
            u.active = True
        s.commit()
    h = {"Authorization": "Bearer " + create_token(1, 961)}
    c = TestClient(app)
    r = c.put("/api/v1/projects/961/aksk/govak",
              json={"ip_allowlist": ["192.0.2.0/24"],
                    "rate_limit_per_min": 5}, headers=h)
    assert r.status_code == 200
    assert r.json()["rate_limit_per_min"] == 5
    assert c.put("/api/v1/projects/961/aksk/govak",
                 json={"ip_allowlist": ["bad-cidr"]},
                 headers=h).status_code == 400
