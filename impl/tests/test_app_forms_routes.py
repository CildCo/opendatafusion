from sqlalchemy import create_engine, text

from fastapi.testclient import TestClient

from odf.assets.service import create_asset, publish_asset
from odf.db import SessionLocal
from odf.main import app
from odf.models import Datasource, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "id"}, {"column": "city"}, {"column": "amount"}],
    "filters": [], "limit": 100},
    "params": [], "sql": None, "auth": None}


def _user(uid, role):
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="form_u%d" % uid, password_hash="x",
                     role=role, active=True)
            s.add(u)
        else:
            u.role = role
            u.active = True
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "r.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id integer primary key, "
                       "city text, amount int)"))
        c.execute(text("insert into t values (1, 'a', 10)"))
    with SessionLocal() as s:
        if not s.get(Datasource, 1):
            s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                             dsn_encrypted=encrypt_secret(url)))
        else:
            s.get(Datasource, 1).dsn_encrypted = encrypt_secret(url)
        s.commit()
        ds = create_asset(s, 1, "dataset", "D", DATASET, "admin",
                          enabled=False)
        publish_asset(s, ds.id, "admin")
        dsid = ds.id
        content = {"start_page": "p1", "pages": [{
            "id": "p1", "title": "P", "params": [], "components": [
                {"id": "f", "type": "form", "dataset_id": dsid,
                 "mode": "insert", "fields": [
                     {"column": "city", "widget": "input",
                      "required": True},
                     {"column": "amount", "widget": "number"}]}]}]}
        a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
        return a.id, dsid, url


def test_submit_and_form_schema(tmp_path):
    _user(1, "admin")
    aid, dsid, url = _env(tmp_path)
    c = TestClient(app)
    h = _h()
    schema = c.get(f"/api/v1/apps/{aid}/form-schema",
                   params={"dataset_id": dsid}, headers=h)
    assert schema.status_code == 200
    assert schema.json()["columns"] == ["id", "city", "amount"]
    r = c.post(f"/api/v1/apps/{aid}/submit",
               json={"component_id": "f",
                     "values": {"city": "x", "amount": 4}}, headers=h)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "mode": "insert", "affected": 1}
    raw = create_engine(url)
    with raw.connect() as conn:
        assert conn.execute(text("select count(*) from t")).scalar() == 2


def test_submit_errors_and_project_isolation(tmp_path):
    _user(1, "admin")
    aid, dsid, _ = _env(tmp_path)
    c = TestClient(app)
    h = _h()
    missing = c.post(f"/api/v1/apps/{aid}/submit",
                     json={"component_id": "f",
                           "values": {"amount": 4}}, headers=h)
    assert missing.status_code == 400
    unknown = c.post(f"/api/v1/apps/{aid}/submit",
                     json={"component_id": "f",
                           "values": {"city": "x", "nope": 1}}, headers=h)
    assert unknown.status_code == 400
    assert c.get(f"/api/v1/apps/{aid}/form-schema",
                 params={"dataset_id": dsid}, headers=_h(1, 4)).status_code == 404
    assert c.post(f"/api/v1/apps/{aid}/submit",
                  json={"component_id": "f", "values": {}},
                  headers=_h(1, 4)).status_code == 404


def test_published_submission_uses_published_form(tmp_path):
    _user(1, "admin")
    aid, dsid, _ = _env(tmp_path)
    c = TestClient(app)
    h = _h()
    from odf.models import Asset, AssetVersion
    from odf.assets.service import update_draft
    from odf.services.approval import issue_token
    with SessionLocal() as s:
        a = s.get(Asset, aid)
        content = s.get(AssetVersion, a.draft_version_id).content_json
        content["pages"][0]["components"][0]["fields"] = [
            {"column": "amount", "widget": "number"}]
        update_draft(s, aid, content, "admin")
    c.post(f"/api/v1/apps/{aid}/publish?approval_token="
           + issue_token(aid, "publish_app"), headers=h)
    with SessionLocal() as s:
        a = s.get(Asset, aid)
        content = s.get(AssetVersion, a.draft_version_id).content_json
        content["pages"][0]["components"][0]["fields"] = [
            {"column": "city", "widget": "input", "required": True},
            {"column": "amount", "widget": "number"}]
        update_draft(s, aid, content, "admin")
    r = c.post(f"/api/v1/apps/{aid}/submit",
               json={"component_id": "f",
                     "values": {"city": "draft-only"},
                     "published": True}, headers=h)
    assert r.status_code == 400
    ok = c.post(f"/api/v1/apps/{aid}/submit",
                json={"component_id": "f", "values": {"amount": 9},
                      "published": True}, headers=h)
    assert ok.status_code == 200


def test_viewer_cannot_override_form_definition(tmp_path):
    _user(1, "admin")
    aid, dsid, _ = _env(tmp_path)
    c = TestClient(app)
    from odf.services.approval import issue_token
    c.post(f"/api/v1/apps/{aid}/publish?approval_token="
           + issue_token(aid, "publish_app"), headers=_h())
    _user(1, "viewer")
    h = _h()
    forged = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [], "components": [
            {"id": "f", "type": "form", "dataset_id": dsid,
             "mode": "insert", "fields": [
                 {"column": "id", "widget": "number"}]}]}]}
    r = c.post(f"/api/v1/apps/{aid}/submit",
               json={"component_id": "f", "values": {"id": 5},
                     "content": forged}, headers=h)
    assert r.status_code == 400
    ok = c.post(f"/api/v1/apps/{aid}/submit",
                json={"component_id": "f",
                      "values": {"city": "x", "amount": 1}}, headers=h)
    assert ok.status_code == 200


def test_restricted_form_requires_role(tmp_path):
    _user(1, "admin")
    aid, dsid, _ = _env(tmp_path)
    with SessionLocal() as s:
        content = {"start_page": "p1", "pages": [{
            "id": "p1", "title": "P", "params": [], "components": [
                {"id": "f", "type": "form", "dataset_id": dsid,
                 "mode": "insert", "allow_roles": ["editor"],
                 "fields": [{"column": "city", "widget": "input"}]}]}]}
        rid = create_asset(s, 1, "app", "R", content, "admin",
                           enabled=False).id
    c = TestClient(app)
    from odf.services.approval import issue_token
    c.post(f"/api/v1/apps/{rid}/publish?approval_token="
           + issue_token(rid, "publish_app"), headers=_h())
    _user(1, "viewer")
    denied = c.post(f"/api/v1/apps/{rid}/submit",
                    json={"component_id": "f", "values": {"city": "x"}},
                    headers=_h())
    assert denied.status_code == 403
    _user(1, "editor")
    ok = c.post(f"/api/v1/apps/{rid}/submit",
                json={"component_id": "f", "values": {"city": "x"}},
                headers=_h())
    assert ok.status_code == 200


def test_delete_form_over_http(tmp_path):
    _user(1, "editor")
    aid, dsid, url = _env(tmp_path)
    with SessionLocal() as s:
        content = {"start_page": "p1", "pages": [{
            "id": "p1", "title": "P", "params": [], "components": [
                {"id": "d", "type": "form", "dataset_id": dsid,
                 "mode": "delete", "key": "id",
                 "fields": [{"column": "id", "widget": "number",
                             "required": True}]}]}]}
        did = create_asset(s, 1, "app", "Del", content, "admin",
                           enabled=False).id
    c = TestClient(app)
    r = c.post(f"/api/v1/apps/{did}/submit",
               json={"component_id": "d", "values": {"id": 1}},
               headers=_h())
    assert r.status_code == 200
    assert r.json()["mode"] == "delete"
    raw = create_engine(url)
    with raw.connect() as conn:
        assert conn.execute(text("select count(*) from t")).scalar() == 0


def test_inactive_user_cannot_submit(tmp_path):
    _user(1, "editor")
    aid, dsid, _ = _env(tmp_path)
    c = TestClient(app)
    h = _h()
    with SessionLocal() as s:
        u = s.get(User, 1)
        u.active = False
        s.commit()
    assert c.post(f"/api/v1/apps/{aid}/submit",
                  json={"component_id": "f",
                        "values": {"city": "x"}}, headers=h).status_code == 401
    with SessionLocal() as s:
        u = s.get(User, 1)
        u.active = True
        s.commit()


def test_viewer_cannot_use_draft_form_policy(tmp_path):
    _user(1, "admin")
    aid, dsid, _ = _env(tmp_path)
    from odf.models import Asset, AssetVersion
    from odf.assets.service import update_draft
    from odf.services.approval import issue_token
    with SessionLocal() as s:
        a = s.get(Asset, aid)
        content = s.get(AssetVersion, a.draft_version_id).content_json
        content["pages"][0]["components"][0]["allow_roles"] = ["editor"]
        update_draft(s, aid, content, "admin")
    c = TestClient(app)
    c.post(f"/api/v1/apps/{aid}/publish?approval_token="
           + issue_token(aid, "publish_app"), headers=_h())
    with SessionLocal() as s:
        a = s.get(Asset, aid)
        content = s.get(AssetVersion, a.draft_version_id).content_json
        content["pages"][0]["components"][0]["allow_roles"] = ["viewer"]
        update_draft(s, aid, content, "admin")
    _user(1, "viewer")
    r = c.post(f"/api/v1/apps/{aid}/submit",
               json={"component_id": "f",
                     "values": {"city": "x", "amount": 1}},
               headers=_h())
    assert r.status_code == 403


def test_inactive_approver_cannot_approve(tmp_path):
    _user(1, "approver")
    aid, dsid, _ = _env(tmp_path)
    from odf.models import User
    from odf.services.changes import propose
    with SessionLocal() as s:
        cid = propose(s, 1, "approver", "app_form_submit", aid).id
        u = s.get(User, 1)
        u.active = False
        s.commit()
    c = TestClient(app)
    assert c.post(f"/api/v1/changes/{cid}/approve",
                  headers=_h()).status_code == 401
    with SessionLocal() as s:
        u = s.get(User, 1)
        u.active = True
        s.commit()
