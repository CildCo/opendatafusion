from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.mcp.server import TOOLS
from odf.models import LineageEdge

VALID = {"nodes": [
    {"id": "s", "type": "source", "config": {}},
    {"id": "o", "type": "sink", "config": {}}],
    "edges": [{"from": "s", "to": "o"}]}


def test_list_and_get_asset():
    with SessionLocal() as s:
        a = create_asset(s, 1, "pipeline", "mcp-list", VALID, "mcp")
        aid = a.id
    rows = TOOLS["list_assets"](type="pipeline", project_id=1)
    assert any(r["id"] == aid for r in rows)
    got = TOOLS["get_asset"](asset_id=aid)
    assert got["type"] == "pipeline" and got["draft"]["nodes"]
    assert got["published"] is None


def test_lineage_returns_dag_edges():
    with SessionLocal() as s:
        a = create_asset(s, 1, "pipeline", "mcp-lineage", VALID, "mcp")
        aid = a.id
        s.add(LineageEdge(project_id=1, from_type="table",
                          from_id="demo", from_ref="demo",
                          to_type="asset", to_id=str(aid), to_ref="mcp"))
        s.commit()
    out = TOOLS["lineage"](project_id=1, asset_id=aid)
    assert {"from": "s", "to": "o"} in out["pipeline_edges"]
    assert any(e["to_id"] == str(aid) for e in out["edges"])


def test_snapshot_has_assets_and_jobs():
    snapshot = TOOLS["platform_snapshot"]()
    assert "assets" in snapshot and "jobs" in snapshot
