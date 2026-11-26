from fastapi.testclient import TestClient

from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.auth import create_token


def _user(uid, username, role):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username=username, password_hash="x",
                        role=role, active=True)
            s.add(user)
        else:
            user.role = role
            user.active = True
        s.commit()


def _h(uid=1, project=1):
    return {"Authorization": "Bearer " + create_token(uid, project)}


def test_asset_catalog_routes_and_role_gate():
    _user(41, "asset-cat-viewer", "viewer")
    _user(42, "asset-cat-approver", "approver")
    with SessionLocal() as s:
        asset = create_asset(s, 1, "dataset", "route asset", {
            "mode": "visual",
            "query": {"datasource_id": 1, "table": "t",
                      "select": [{"column": "id"}], "limit": 100},
            "params": [], "sql": None, "auth": None},
            "asset-cat-viewer", enabled=False)
        aid = asset.id
    c = TestClient(app)
    listed = c.get("/api/v1/catalog/assets?q=route", headers=_h(41))
    assert listed.status_code == 200
    assert any(item["id"] == aid for item in listed.json()["items"])
    denied = c.post(
        "/api/v1/catalog/assets/%d/certification" % aid,
        json={"certified": True, "note": "reviewed"}, headers=_h(41))
    assert denied.status_code == 403
    ok = c.post(
        "/api/v1/catalog/assets/%d/certification" % aid,
        json={"certified": True, "note": "reviewed"}, headers=_h(42))
    assert ok.status_code == 200
    assert ok.json()["certification"] == "certified"
    similar = c.get(
        "/api/v1/catalog/assets/%d/similar" % aid, headers=_h(41))
    assert similar.status_code == 200
    lifecycle = c.post(
        "/api/v1/catalog/assets/%d/lifecycle" % aid,
        json={"lifecycle": "deprecated", "note": "replaced"},
        headers=_h(42))
    assert lifecycle.status_code == 200
    assert lifecycle.json()["certification"] == "none"
