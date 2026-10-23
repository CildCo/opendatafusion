from fastapi.testclient import TestClient

from odf.main import app
from odf.services.auth import create_token


def test_catalog_requires_auth():
    assert TestClient(app).get("/api/v1/mcp/tools").status_code == 401


def test_catalog_lists_tools():
    token = create_token(1, 1)
    r = TestClient(app).get(
        "/api/v1/mcp/tools",
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200
    names = {t["name"] for t in r.json()}
    assert {"list_assets", "preview_node", "publish_pipeline"} <= names


def test_tool_permission_error_maps_to_403():
    token = create_token(1, 1)
    r = TestClient(app).post(
        "/api/v1/mcp/publish_pipeline",
        json={"asset_id": 999, "approval_token": "bad"},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 403


def test_tool_validation_returns_structured_result():
    token = create_token(1, 1)
    r = TestClient(app).post(
        "/api/v1/mcp/validate_pipeline",
        json={"content": {"nodes": [], "edges": []}},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200
    assert r.json()["valid"] is False


def _user(uid, role):
    from odf.db import SessionLocal
    from odf.models import User
    with SessionLocal() as s:
        u = s.get(User, uid)
        if not u:
            u = User(id=uid, username="mcp_u%d" % uid,
                     password_hash="x", role=role, active=True)
            s.add(u)
        else:
            u.role = role
        s.commit()


def test_cross_project_asset_is_rejected():
    from odf.assets.service import create_asset
    from odf.db import SessionLocal
    _user(1, "admin")
    with SessionLocal() as s:
        a = create_asset(s, 2, "pipeline", "other-project",
                         {"nodes": [], "edges": []}, "admin")
        aid = a.id
    token = create_token(1, 1)
    r = TestClient(app).post(
        "/api/v1/mcp/get_asset", json={"asset_id": aid},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 403


def test_viewer_cannot_update_draft():
    from odf.assets.service import create_asset
    from odf.db import SessionLocal
    _user(1, "admin")
    _user(2, "viewer")
    with SessionLocal() as s:
        a = create_asset(s, 1, "pipeline", "viewer-target",
                         {"nodes": [], "edges": []}, "admin")
        aid = a.id
    token = create_token(2, 1)
    r = TestClient(app).post(
        "/api/v1/mcp/update_pipeline_draft",
        json={"asset_id": aid, "content": {"nodes": [], "edges": []}},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 403


def test_wrong_action_and_expired_tokens_are_rejected():
    from odf.assets.service import create_asset
    from odf.db import SessionLocal
    from odf.services.approval import issue_token
    _user(1, "admin")
    with SessionLocal() as s:
        a = create_asset(s, 1, "pipeline", "token-target",
                         {"nodes": [], "edges": []}, "admin", enabled=False)
        aid = a.id
    token = create_token(1, 1)
    headers = {"Authorization": "Bearer " + token}
    wrong = issue_token(aid, "rollback_pipeline")
    assert TestClient(app).post(
        "/api/v1/mcp/publish_pipeline",
        json={"asset_id": aid, "approval_token": wrong},
        headers=headers).status_code == 403
    expired = issue_token(aid, "publish_pipeline", ttl_s=-1)
    assert TestClient(app).post(
        "/api/v1/mcp/publish_pipeline",
        json={"asset_id": aid, "approval_token": expired},
        headers=headers).status_code == 403


def test_pipeline_run_error_maps_to_400(monkeypatch):
    from odf.mcp.server import TOOLS
    from odf.pipeline.runner import PipelineRunError
    _user(1, "admin")

    def boom(**kwargs):
        raise PipelineRunError("s", "boom", {"s": {"status": "failed"}})

    monkeypatch.setitem(TOOLS, "preview_node", boom)
    token = create_token(1, 1)
    r = TestClient(app).post(
        "/api/v1/mcp/preview_node",
        json={"asset_id": 1, "node_id": "s"},
        headers={"Authorization": "Bearer " + token})
    assert r.status_code == 400
    assert r.json()["detail"]["node_id"] == "s"
