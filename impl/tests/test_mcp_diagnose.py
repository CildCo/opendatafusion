from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.mcp.server import TOOLS
from odf.models import Job, PipelineNodeRun

VALID = {"nodes": [
    {"id": "s", "type": "source", "config": {}},
    {"id": "o", "type": "sink", "config": {}}],
    "edges": [{"from": "s", "to": "o"}]}


def test_diagnose_failed_job_points_at_node():
    with SessionLocal() as s:
        a = create_asset(s, 1, "pipeline", "diag", VALID, "mcp")
        job = Job(asset_id=a.id, asset_type="pipeline", status="failed",
                  attempts=3, last_error="target down")
        s.add(job)
        s.flush()
        s.add(PipelineNodeRun(job_id=job.id, asset_id=a.id, node_id="o",
                              status="failed", error="target down"))
        s.commit()
        jid = job.id
    out = TOOLS["diagnose_run"](run_id=jid)
    assert out["job"]["status"] == "failed"
    assert out["nodes"][0]["node_id"] == "o"
    assert any("target down" in h for h in out["hints"])
    assert out["evidence"]
