import pytest

from odf.mcp.server import TOOLS, assert_read_only
from odf.services.approval import issue_token, verify_token


def test_tools_registered():
    for name in ["platform_snapshot", "list_flows", "flow_health",
                 "query_sql", "pause_flow", "resume_flow"]:
        assert name in TOOLS


def test_approval_token_binds_action():
    t = issue_token(1, "pause", ttl_s=60)
    assert verify_token(1, "pause", t) is True
    assert verify_token(1, "resume", t) is False


def test_query_sql_rejects_data_modifying_cte():
    with pytest.raises(ValueError):
        assert_read_only(
            "WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d")


def test_query_sql_accepts_plain_select():
    assert_read_only("select * from t")


def test_mcp_http_endpoint_requires_auth():
    from fastapi.testclient import TestClient
    from odf.main import app
    assert TestClient(app).post("/api/v1/mcp/platform_snapshot",
                                json={}).status_code == 401


def test_mcp_http_endpoint_works_with_token():
    from fastapi.testclient import TestClient
    from odf.main import app
    from odf.services.auth import create_token
    token = create_token(1, 2)
    r = TestClient(app).post("/api/v1/mcp/platform_snapshot", json={},
                             headers={"Authorization": "Bearer " + token})
    assert r.status_code == 200


def test_mcp_server_registers_tools():
    from odf.mcp.http import server
    assert server.name == "odf"


def test_mcp_http_app_rejects_missing_token():
    from starlette.testclient import TestClient
    from odf.mcp.http import app
    c = TestClient(app())
    assert c.post("/mcp", json={}).status_code == 401


def test_mcp_http_accepts_valid_token_and_lists_tools():
    from starlette.testclient import TestClient
    from odf.mcp.http import app
    from odf.db import SessionLocal
    from odf.models import User
    from odf.services.auth import create_token
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="mcp-test", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        u.active = True
        s.commit()
    token = create_token(1, 1)
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/json, text/event-stream"}
    with TestClient(app()) as c:
        r = c.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-03-26",
                       "capabilities": {},
                       "clientInfo": {"name": "test", "version": "1"}}})
        assert r.status_code == 200
        sid = r.headers["mcp-session-id"]
        headers["mcp-session-id"] = sid
        r = c.post("/mcp", headers=headers, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/list",
            "params": {}})
        assert r.status_code == 200 and "platform_snapshot" in r.text
