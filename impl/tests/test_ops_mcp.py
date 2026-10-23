from datetime import datetime, timezone

from odf.db import SessionLocal
from odf.mcp.server import CURRENT_PROJECT, TOOLS
from odf.models import Flow, Job, Project


def test_ops_tools_registered():
    for name in ("ops_summary", "list_jobs", "list_alerts"):
        assert name in TOOLS
    for name in ("retry_job", "ack_alert"):
        assert name in TOOLS


def _fixture():
    with SessionLocal() as s:
        for pid, code in ((905, "ops905"), (906, "ops906")):
            if not s.get(Project, pid):
                s.add(Project(id=pid, code=code, name=code))
        s.flush()
        s.query(Job).filter(Job.id.in_([9361, 9362])).delete(
            synchronize_session=False)
        s.query(Flow).filter(Flow.id.in_([9161, 9162])).delete(
            synchronize_session=False)
        s.add_all([
            Flow(id=9161, project_id=905, name="mcp-ops"),
            Flow(id=9162, project_id=906, name="mcp-other"),
            Job(id=9361, flow_id=9161, status="failed", attempts=3,
                last_error="boom", finished_at=datetime.now(timezone.utc)),
            Job(id=9362, flow_id=9162, status="failed", attempts=3,
                last_error="other"),
        ])
        s.commit()


def test_ops_tools_are_project_scoped():
    _fixture()
    token = CURRENT_PROJECT.set(905)
    try:
        jobs = TOOLS["list_jobs"]()
        assert [j["id"] for j in jobs] == [9361]
        out = TOOLS["ops_summary"]()
        assert out["jobs"]["failed"] == 1
        retried = TOOLS["retry_job"](job_id=9361)
        assert retried["status"] == "queued"
    finally:
        CURRENT_PROJECT.reset(token)


def test_ops_tools_require_a_project():
    import pytest
    with pytest.raises(PermissionError):
        TOOLS["ops_summary"]()
    with pytest.raises(PermissionError):
        TOOLS["list_jobs"]()


def test_ops_tools_accept_explicit_project():
    _fixture()
    assert [j["id"] for j in TOOLS["list_jobs"](project_id=905)] == [9361]
