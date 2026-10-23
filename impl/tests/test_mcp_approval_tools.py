import pytest
from sqlalchemy import create_engine, text

from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.mcp.server import TOOLS
from odf.models import Datasource
from odf.services.approval import issue_token
from odf.services.crypto import encrypt_secret

PIPE = {"nodes": [
    {"id": "s", "type": "source",
     "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
    {"id": "o", "type": "sink",
     "config": {"datasource_id": 1, "table": "t", "pk": ["id"]}}],
    "edges": [{"from": "s", "to": "o"}]}
API = {"mode": "sql", "query": {"datasource_id": 1},
       "sql": "select 1 as n", "params": [],
       "auth": {"type": "aksk", "rate_limit_per_min": 60}}


def test_publish_requires_bound_token(tmp_path):
    url = "sqlite:///" + str(tmp_path / "mcp.db")
    with create_engine(url).begin() as c:
        c.execute(text("create table t (id int)"))
    with SessionLocal() as s:
        ds = s.get(Datasource, 1)
        if ds:
            ds.dsn_encrypted = encrypt_secret(url)
            ds.kind = "sqlite"
        else:
            s.add(Datasource(id=1, project_id=1, name="mcp-ds",
                             kind="sqlite",
                             dsn_encrypted=encrypt_secret(url)))
            s.commit()
        a = create_asset(s, 1, "pipeline", "mcp-pub", PIPE, "mcp",
                         enabled=False)
        aid = a.id
    with pytest.raises(PermissionError):
        TOOLS["publish_pipeline"](asset_id=aid, approval_token="bad")
    out = TOOLS["publish_pipeline"](
        asset_id=aid, approval_token=issue_token(aid, "publish_pipeline"))
    assert out["version"] == 1


def test_api_publish_and_revoke():
    with SessionLocal() as s:
        if not s.get(Datasource, 1):
            s.add(Datasource(id=1, project_id=1, name="mcp-ds",
                             kind="sqlite", dsn_encrypted="x"))
            s.commit()
        a = create_asset(s, 1, "api", "mcp-api", API, "mcp", enabled=False)
        aid = a.id
    TOOLS["publish_api"](
        asset_id=aid, approval_token=issue_token(aid, "publish_api"))
    assert TOOLS["get_asset"](asset_id=aid)["enabled"] is True
    TOOLS["revoke_api"](
        asset_id=aid, approval_token=issue_token(aid, "revoke_api"))
    assert TOOLS["get_asset"](asset_id=aid)["enabled"] is False
