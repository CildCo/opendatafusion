from odf.mcp.server import TOOLS


def test_dashboard_tool_registered():
    assert "dashboard_data" in TOOLS


def test_dashboard_tool_accepts_params():
    from odf.assets.service import create_asset, publish_asset
    from odf.db import SessionLocal
    content = {"params": [{"name": "city", "type": "string",
                           "default": "a"}],
               "widgets": [{"id": "t", "type": "text", "text": "x",
                            "x": 0, "y": 0, "w": 3, "h": 2}]}
    with SessionLocal() as s:
        a = create_asset(s, 1, "dashboard", "mcp-dash-params", content,
                         "mcp", enabled=False)
        aid = a.id
        publish_asset(s, aid, "mcp")
    out = TOOLS["dashboard_data"](asset_id=aid, params={"city": "b"})
    assert out["params"]["city"] == "b"
