import base64
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base, SessionLocal
from odf.main import app
from odf.models import AkSk, Datasource, Project, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret

QUERY = "query($city: String) { %s(city: $city) { total rows } }"


def _env(tmp_path):
    import uuid
    from odf.db import SessionLocal
    url = "sqlite:///" + str(tmp_path / "g.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
        c.execute(text("insert into t values ('a',10),('a',5),('b',7)"))
    suffix = uuid.uuid4().hex[:8]
    with SessionLocal() as s:
        if not s.get(Project, 9401):
            s.add(Project(id=9401, code="gqlp", name="GQL", status=1))
        if not s.get(User, 9401):
            s.add(User(id=9401, username="gql_user", password_hash="x",
                       role="admin", active=True))
        ds = Datasource(project_id=9401, name="gql_%s" % suffix,
                        kind="sqlite", dsn_encrypted=encrypt_secret(url))
        s.add(ds)
        s.flush()
        ak, sk = "gql_ak_%s" % suffix, "gql_sk_%s" % suffix
        s.add(AkSk(project_id=9401, ak=ak,
                   sk_encrypted=encrypt_secret(sk)))
        s.commit()
        asset = create_asset(s, 9401, "api", "orders", {
            "mode": "sql", "query": {"datasource_id": ds.id},
            "sql": "select city, amount from t where city = ${city}",
            "params": [{"name": "city", "type": "string",
                        "required": False}],
            "auth": {"type": "aksk"}}, "admin", enabled=False,
            key="gql_%s" % suffix)
        publish_asset(s, asset.id, "admin")
        return url, s, asset, ak, sk


def _headers(ak, sk, path, body):
    date = str(int(time.time() * 1000))
    md5 = base64.b64encode(hashlib.md5(body).digest()).decode()
    s2s = "\n".join(["POST", md5, "application/json", date, path])
    sig = base64.b64encode(
        hmac.new(sk.encode(), s2s.encode(), hashlib.sha1).digest()).decode()
    return {"Authorization": ak + ":" + sig, "projectKey": "gqlp",
            "Content-Type": "application/json", "Date": date}


def test_graphql_query_and_introspection(tmp_path):
    _, s, asset, ak, sk = _env(tmp_path)
    body = json.dumps({"query": QUERY % asset.key,
                       "variables": {"city": "a"}}).encode()
    client = TestClient(app)
    response = client.post("/openapi/graphql", content=body,
                           headers=_headers(ak, sk, "/openapi/graphql", body))
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload.get("errors") is None
    result = payload["data"][asset.key]
    assert result["total"] == 2
    assert len(result["rows"]) == 2

    body = json.dumps({"query": "{ __schema { queryType { fields "
                                "{ name } } } }"}).encode()
    response = client.post("/openapi/graphql", content=body,
                           headers=_headers(ak, sk, "/openapi/graphql", body))
    names = [f["name"] for f in response.json()["data"]["__schema"]
             ["queryType"]["fields"]]
    assert asset.key in names


def test_graphql_rejects_unknown_field(tmp_path):
    _, s, _, ak, sk = _env(tmp_path)
    body = json.dumps({"query": "{ not_a_field { total } }"}).encode()
    response = TestClient(app).post(
        "/openapi/graphql", content=body,
        headers=_headers(ak, sk, "/openapi/graphql", body))
    assert response.status_code == 200
    assert response.json()["errors"]


def test_graphql_schema_endpoint(tmp_path):
    _, s, asset, ak, sk = _env(tmp_path)
    headers = {"Authorization": "Bearer " + create_token(9401, 9401)}
    r = TestClient(app).get("/api/v1/apis/graphql/schema", headers=headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["endpoint"] == "/openapi/graphql"
    assert asset.key in payload["sdl"]
    assert "total" in payload["example"] and "rows" in payload["example"]


def test_graphql_requires_signature(tmp_path):
    _, s, asset, ak, sk = _env(tmp_path)
    body = json.dumps({"query": "{ _empty }"}).encode()
    r = TestClient(app).post("/openapi/graphql", content=body,
                             headers={"projectKey": "gqlp"})
    assert r.status_code == 401
