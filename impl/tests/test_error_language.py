from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import Project, User
from odf.services.auth import create_token

PROJECT_ID = 9901


def _viewer():
    with SessionLocal() as s:
        if not s.get(Project, PROJECT_ID):
            s.add(Project(id=PROJECT_ID, code="msg", name="Messages",
                          status=1))
        u = s.get(User, 9901)
        if not u:
            u = User(id=9901, username="msg-viewer", password_hash="x",
                     role="viewer", active=True)
            s.add(u)
        u.role, u.active = "viewer", True
        s.commit()


def test_permission_error_follows_accept_language():
    _viewer()
    client = TestClient(app)
    token = create_token(9901, PROJECT_ID)
    body = {"dataset_id": 1, "name": "x", "kind": "not_null"}
    zh = client.post("/api/v1/quality/rules", json=body,
                     headers={"Authorization": "Bearer " + token,
                              "Accept-Language": "zh-CN,zh;q=0.9"})
    en = client.post("/api/v1/quality/rules", json=body,
                     headers={"Authorization": "Bearer " + token,
                              "Accept-Language": "en-US"})
    assert zh.status_code == 403 and zh.json()["detail"] == "需要编辑权限"
    assert en.status_code == 403 and en.json()["detail"] == "Editor role required"


def test_missing_token_follows_accept_language():
    client = TestClient(app)
    zh = client.get("/api/v1/quality/rules",
                    headers={"Accept-Language": "zh-CN"})
    en = client.get("/api/v1/quality/rules")
    assert zh.json()["detail"] == "缺少登录令牌"
    assert en.json()["detail"] == "Missing bearer token"
