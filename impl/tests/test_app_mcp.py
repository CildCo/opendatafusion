from odf.assets.service import create_asset, publish_asset
from odf.db import SessionLocal
from odf.mcp.server import TOOLS


APP = {"start_page": "p1", "pages": [{
    "id": "p1", "title": "P", "params": [],
    "components": [{"id": "t", "type": "text", "text": "mcp"}]}]}


def test_app_tool_registered():
    assert "app_data" in TOOLS


def test_app_tool_reads_published_page():
    with SessionLocal() as s:
        a = create_asset(s, 1, "app", "mcp-app", APP, "mcp",
                         enabled=False)
        aid = a.id
        publish_asset(s, aid, "mcp")
    out = TOOLS["app_data"](asset_id=aid)
    assert out["page_id"] == "p1"
    assert out["components"]["t"]["text"] == "mcp"
