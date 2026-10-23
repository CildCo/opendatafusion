import base64
import hashlib
import hmac
import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from odf.assets.service import create_asset, publish_asset
from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import AkSk, Datasource, Project
from odf.services.aksk import sign, string_to_sign
from odf.services.crypto import encrypt_secret
from odf.services.grants import decide_request, request_access, revoke_grant


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "gw.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
        c.execute(text("insert into t values (1)"))
    with SessionLocal() as s:
        for pid, code in ((951, "gov951"), (952, "gov952")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code, status=1))
        row = s.get(Datasource, 951)
        if row:
            row.dsn_encrypted = encrypt_secret(url)
        else:
            s.add(Datasource(id=951, project_id=951, name="gw",
                             kind="sqlite",
                             dsn_encrypted=encrypt_secret(url)))
        s.commit()
        content = {"mode": "visual",
                   "query": {"datasource_id": 951, "table": "t",
                             "select": [{"column": "id"}]},
                   "params": [], "sql": None}
        a = create_asset(s, 951, "api", "Granted API", content, "admin",
                         enabled=False)
        publish_asset(s, a.id, "admin")
        for ak, pid, sk in (("gak1", 951, "gsk1"),
                            ("gak2", 952, "gsk2")):
            if not s.query(AkSk).filter_by(ak=ak).first():
                s.add(AkSk(project_id=pid, ak=ak,
                           sk_encrypted=encrypt_secret(sk), enabled=True))
        s.commit()
        return a, "gsk2"


def _headers(method, path, ak="gak2", sk="gsk2", project="gov952",
             body=b"{}"):
    date = str(int(time.time() * 1000))
    ctype = "application/json"
    s2s = string_to_sign(method, body, ctype, date, path)
    auth = ak + ":" + sign(sk, s2s)
    return {"projectKey": project, "Authorization": auth, "Date": date,
            "Content-Type": ctype}


def _call(key, ak="gak2", sk="gsk2", project="gov952"):
    path = "/openapi/%s" % key
    return TestClient(app).post(
        path, content=b"{}", headers=_headers("POST", path, ak, sk, project))


def test_gateway_requires_grant_and_honors_revoke(tmp_path):
    a, _ = _env(tmp_path)
    owner = _call(a.key, "gak1", "gsk1", "gov951")
    assert owner.status_code == 200
    denied = _call(a.key)
    assert denied.status_code == 403
    assert "permission" in denied.json()["detail"]
    with SessionLocal() as s:
        req = request_access(s, a.id, 952, "consumer")
        decide_request(s, req["id"], 951, "owner", True)
    ok = _call(a.key)
    assert ok.status_code == 200
    assert ok.json()["results"][0]["id"] == 1
    with SessionLocal() as s:
        from odf.services.grants import list_grants
        gid = list_grants(s, 951)[0]["id"]
        revoke_grant(s, gid, 951, "owner")
    assert _call(a.key).status_code == 403
