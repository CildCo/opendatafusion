from sqlalchemy import create_engine, text

from odf.assets.service import create_asset, publish_asset, update_draft
from odf.db import SessionLocal
from odf.mcp.server import (APPROVER_TOOLS, CURRENT_PROJECT, TOOLS,
                            WRITE_TOOLS)
from odf.models import AuditLog, Datasource
from odf.services.changes import propose
from odf.services.approval import issue_token
from odf.services.crypto import encrypt_secret


def _app(tmp_path):
    url = "sqlite:///" + str(tmp_path / "m.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id integer primary key, city text)"))
    with SessionLocal() as s:
        ds_row = s.get(Datasource, 77)
        if not ds_row:
            s.add(Datasource(id=77, project_id=1, name="mcp-form",
                             kind="sqlite",
                             dsn_encrypted=encrypt_secret(url)))
        else:
            ds_row.dsn_encrypted = encrypt_secret(url)
        s.commit()
        ds = create_asset(s, 1, "dataset", "D", {
            "mode": "visual",
            "query": {"datasource_id": 77, "table": "t",
                      "select": [{"column": "id"}, {"column": "city"}],
                      "limit": 100},
            "params": [], "sql": None, "auth": None}, "admin",
            enabled=False)
        publish_asset(s, ds.id, "admin")
        content = {"start_page": "p1", "pages": [{
            "id": "p1", "title": "P", "params": [], "components": [
                {"id": "f", "type": "form", "dataset_id": ds.id,
                 "mode": "insert", "fields": [
                     {"column": "city", "widget": "input",
                      "required": True}]}]}]}
        a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
        publish_asset(s, a.id, "admin")
        return a.id, url


def test_tool_registered_and_write_approver():
    assert "submit_app_form" in TOOLS
    assert "submit_app_form" in WRITE_TOOLS
    assert "submit_app_form" in APPROVER_TOOLS


def test_bad_token_writes_nothing(tmp_path):
    import pytest
    aid, url = _app(tmp_path)
    with SessionLocal() as s:
        cid = propose(s, 1, "admin", "app_form_submit", aid).id
    try:
        TOOLS["submit_app_form"](
            asset_id=aid, component_id="f", values={"city": "x"},
            approval_token=issue_token(aid, "publish_app"),
            change_id=cid, project_id=1)
    except PermissionError:
        pass
    else:
        raise AssertionError("wrong action token must fail")
    raw = create_engine(url)
    with raw.connect() as c:
        assert c.execute(text("select count(*) from t")).scalar() == 0


def test_valid_token_submits_published_form(tmp_path):
    aid, url = _app(tmp_path)
    with SessionLocal() as s:
        cid = propose(s, 1, "admin", "app_form_submit", aid).id
    token = issue_token(aid, "app_form_submit", nonce=str(cid))
    out = TOOLS["submit_app_form"](
        asset_id=aid, component_id="f", values={"city": "x"},
        approval_token=token, change_id=cid, project_id=1)
    assert out == {"ok": True, "mode": "insert", "affected": 1}
    try:
        TOOLS["submit_app_form"](
            asset_id=aid, component_id="f", values={"city": "replay"},
            approval_token=token, change_id=cid, project_id=1)
    except PermissionError:
        pass
    else:
        raise AssertionError("approval must be single-use")
    raw = create_engine(url)
    with raw.connect() as c:
        assert c.execute(text("select city from t")).scalar() == "x"
    with SessionLocal() as s:
        row = (s.query(AuditLog).filter_by(action="app_submit")
               .order_by(AuditLog.id.desc()).first())
        assert row.actor == "mcp"
        assert "x" not in str(row.detail_json)


def test_draft_is_ignored(tmp_path):
    aid, _ = _app(tmp_path)
    with SessionLocal() as s:
        from odf.models import Asset, AssetVersion
        a = s.get(Asset, aid)
        content = s.get(AssetVersion, a.draft_version_id).content_json
        content["pages"][0]["components"][0]["fields"] = [
            {"column": "id", "widget": "number"}]
        update_draft(s, aid, content, "admin")
    with SessionLocal() as s:
        cid = propose(s, 1, "admin", "app_form_submit", aid).id
    token = issue_token(aid, "app_form_submit", nonce=str(cid))
    out = TOOLS["submit_app_form"](
        asset_id=aid, component_id="f", values={"city": "pub"},
        approval_token=token, change_id=cid, project_id=1)
    assert out["affected"] == 1


def test_tool_respects_project_context(tmp_path):
    import pytest
    aid, _ = _app(tmp_path)
    tok = CURRENT_PROJECT.set(2)
    try:
        with SessionLocal() as s:
            cid = propose(s, 1, "admin", "app_form_submit", aid).id
        with pytest.raises(PermissionError):
            TOOLS["submit_app_form"](
                asset_id=aid, component_id="f", values={"city": "x"},
                approval_token=issue_token(aid, "app_form_submit",
                                           nonce=str(cid)),
                change_id=cid)
    finally:
        CURRENT_PROJECT.reset(tok)


def test_cross_project_change_is_rejected(tmp_path):
    import pytest
    aid, _ = _app(tmp_path)
    with SessionLocal() as s:
        other = create_asset(s, 2, "app", "Other", {
            "start_page": "p1", "pages": [{"id": "p1", "title": "P",
                                           "params": [],
                                           "components": []}]},
                             "admin", enabled=False)
        cid = propose(s, 1, "admin", "app_form_submit", other.id).id
        token = issue_token(other.id, "app_form_submit", nonce=str(cid))
    with pytest.raises(PermissionError):
        TOOLS["submit_app_form"](
            asset_id=other.id, component_id="f", values={"city": "x"},
            approval_token=token, change_id=cid, project_id=1)
    assert aid
