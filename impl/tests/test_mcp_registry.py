from odf.mcp.server import TOOLS, WRITE_TOOLS, tool, tool_catalog
from odf.db import SessionLocal
from odf.models import AuditLog


@tool("test_echo")
def echo_tool(value: int = 1, approval_token: str = ""):
    """Echo a value."""
    return {"value": value}


@tool("test_write_echo", write=True)
def write_echo_tool(value: int = 1, approval_token: str = ""):
    """Write echo."""
    return {"value": value}


def test_registry_catalog_has_schema_and_write_flag():
    names = {t["name"]: t for t in tool_catalog()}
    assert names["test_echo"]["write"] is False
    assert names["test_write_echo"]["write"] is True
    assert names["test_echo"]["parameters"][0]["name"] == "value"
    assert "approval_token" not in {
        p["name"] for p in names["test_write_echo"]["parameters"]
    }


def test_tool_call_is_audited_without_token():
    with SessionLocal() as s:
        before = s.query(AuditLog).filter_by(action="test_echo").count()
    TOOLS["test_echo"](value=7, approval_token="secret-token")
    with SessionLocal() as s:
        after = s.query(AuditLog).filter_by(action="test_echo").count()
        row = (s.query(AuditLog).filter_by(action="test_echo")
               .order_by(AuditLog.id.desc()).first())
    assert after == before + 1
    assert "approval_token" not in str(row.detail_json)
    assert "secret-token" not in str(row.detail_json)


def test_failed_tool_is_audited():
    @tool("test_fail")
    def fail():
        raise ValueError("boom")

    try:
        TOOLS["test_fail"]()
    except ValueError:
        pass
    with SessionLocal() as s:
        row = (s.query(AuditLog).filter_by(action="test_fail")
               .order_by(AuditLog.id.desc()).first())
    assert row is not None and row.detail_json["ok"] is False


def test_existing_mutation_tools_are_marked_write():
    names = {t["name"]: t for t in tool_catalog()}
    for name in ("propose_change", "apply_change", "pause_pipeline",
                 "resume_pipeline", "publish_api"):
        assert names[name]["write"] is True


def test_pause_pipeline_audits_once_and_commits():
    from odf.models import Asset
    from odf.services.approval import issue_token
    with SessionLocal() as s:
        a = Asset(project_id=1, type="pipeline", key="audit-pipe",
                  name="audit-pipeline", owner="admin", enabled=True)
        s.add(a)
        s.commit()
        aid = a.id
        before = (s.query(AuditLog)
                  .filter_by(action="pause_pipeline").count())
    TOOLS["pause_pipeline"](asset_id=aid,
                            approval_token=issue_token(aid,
                                                       "pause_pipeline"))
    with SessionLocal() as s:
        after = (s.query(AuditLog)
                 .filter_by(action="pause_pipeline").count())
        row = (s.query(AuditLog).filter_by(action="pause_pipeline")
               .order_by(AuditLog.id.desc()).first())
        assert after == before + 1
        assert row.target == str(aid)
        assert s.get(Asset, aid).enabled is False
