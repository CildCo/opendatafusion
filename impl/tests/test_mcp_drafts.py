from sqlalchemy import create_engine, text

from odf.db import SessionLocal
from odf.mcp.server import TOOLS
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

VALID = {"nodes": [
    {"id": "s", "type": "source", "config": {}},
    {"id": "o", "type": "sink", "config": {}}],
    "edges": [{"from": "s", "to": "o"}]}


def test_create_update_pipeline_draft():
    out = TOOLS["create_pipeline_draft"](
        name="ai-draft", content=VALID, project_id=1)
    assert out["id"] and out["key"]
    assert TOOLS["validate_pipeline"](content=VALID)["valid"] is False
    updated = TOOLS["update_pipeline_draft"](
        asset_id=out["id"], content={**VALID, "settings": {"batch": 20}})
    assert updated["version"] == 2
    got = TOOLS["get_asset"](asset_id=out["id"])
    assert got["draft"]["settings"]["batch"] == 20


def test_create_api_draft():
    content = {"mode": "sql", "query": {"datasource_id": 1},
               "sql": "select 1 as n", "params": [],
               "auth": {"type": "aksk", "rate_limit_per_min": 60}}
    out = TOOLS["create_api_draft"](name="ai-api", content=content,
                                    project_id=1)
    assert out["id"] and out["key"]
    got = TOOLS["get_asset"](asset_id=out["id"])
    assert got["type"] == "api"


def test_validate_pipeline_with_schema(tmp_path):
    url = "sqlite:///" + str(tmp_path / "v.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
        c.execute(text("create table dst (id int)"))
    with SessionLocal() as s:
        ds = Datasource(project_id=1, name="mcp-v", kind="sqlite",
                        dsn_encrypted=encrypt_secret(url))
        s.add(ds)
        s.commit()
        content = {"nodes": [
            {"id": "s", "type": "source",
             "config": {"datasource_id": ds.id, "table": "src", "pk": "id"}},
            {"id": "o", "type": "sink",
             "config": {"datasource_id": ds.id, "table": "dst",
                        "pk": ["id"]}}],
            "edges": [{"from": "s", "to": "o"}]}
    out = TOOLS["validate_pipeline"](content=content)
    assert out["valid"] is True, out["errors"]


def test_update_api_draft_rejects_pipeline_asset():
    import pytest
    out = TOOLS["create_pipeline_draft"](
        name="type-mismatch", content=VALID, project_id=1)
    with pytest.raises(ValueError):
        TOOLS["update_api_draft"](asset_id=out["id"], content={})
