from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset, update_draft
from odf.db import Base
from odf.models import AssetVersion, Project, ShareLink
from odf.share.service import (create_share, list_shares, public_data,
                               public_view, resolve, revoke_share)

APP = {"start_page": "p1", "pages": [{
    "id": "p1", "title": "P",
    "params": [{"name": "city", "type": "string", "default": "a"}],
    "components": [
        {"id": "t", "type": "text", "text": "published"}]}]}


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="s1", name="s1"),
               Project(id=2, code="s2", name="s2")])
    s.commit()
    return s


def test_create_list_revoke_hashes_token():
    s = _env()
    a = create_asset(s, 1, "app", "A", APP, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    out = create_share(s, 1, a.id, "app", 7, "admin")
    assert len(out["token"]) > 20
    assert out["expires_at"] > datetime.now(timezone.utc)
    row = s.get(ShareLink, out["id"])
    assert row.token_hash != out["token"]
    assert len(row.token_hash) == 64
    listed = list_shares(s, 1, a.id, "app")
    assert listed[0]["id"] == out["id"]
    assert "token" not in listed[0]
    assert resolve(s, out["token"])[0].id == a.id
    revoke_share(s, 1, a.id, "app", out["id"], "admin")
    with pytest.raises(ValueError):
        resolve(s, out["token"])


def test_expired_unpublished_and_wrong_project():
    s = _env()
    a = create_asset(s, 1, "app", "A", APP, "admin", enabled=False)
    with pytest.raises(ValueError):
        create_share(s, 1, a.id, "app", 7, "admin")
    publish_asset(s, a.id, "admin")
    with pytest.raises(ValueError):
        create_share(s, 2, a.id, "app", 7, "admin")
    out = create_share(s, 1, a.id, "app", 7, "admin")
    row = s.get(ShareLink, out["id"])
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    s.commit()
    with pytest.raises(ValueError):
        resolve(s, out["token"])


def test_public_view_uses_published_and_strips_forms():
    s = _env()
    a = create_asset(s, 1, "app", "A", APP, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    v = s.get(AssetVersion, a.published_version_id)
    v.content_json["pages"][0]["components"].append(
        {"id": "f", "type": "form", "dataset_id": 1, "mode": "insert",
         "fields": [{"column": "city", "widget": "input"}]})
    s.commit()
    draft = {**APP, "pages": [{**APP["pages"][0], "components": [
        {"id": "t", "type": "text", "text": "draft"}]}]}
    update_draft(s, a.id, draft, "admin")
    out = create_share(s, 1, a.id, "app", 7, "admin")
    view = public_view(s, out["token"])
    assert view["kind"] == "app" and view["name"] == "A"
    comps = view["content"]["pages"][0]["components"]
    assert [c["type"] for c in comps] == ["text"]
    assert comps[0]["text"] == "published"
    data = public_data(s, out["token"], params={"city": "b"})
    assert data["params"]["city"] == "b"
    assert data["components"]["t"]["text"] == "published"


def test_dashboard_share():
    s = _env()
    content = {"params": [{"name": "p", "type": "string"}], "widgets": [
        {"id": "t", "type": "text", "text": "dash",
         "x": 0, "y": 0, "w": 3, "h": 2}]}
    a = create_asset(s, 1, "dashboard", "D", content, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    out = create_share(s, 1, a.id, "dashboard", 1, "admin")
    view = public_view(s, out["token"])
    assert view["kind"] == "dashboard"
    data = public_data(s, out["token"], params={"p": "x"})
    assert data["widgets"]["t"]["text"] == "dash"
    assert data["params"]["p"] == "x"


def test_public_data_hides_sql_and_errors(tmp_path):
    from sqlalchemy import text
    from odf.assets.service import create_asset as _create
    from odf.models import Datasource
    from odf.services.crypto import encrypt_secret
    url = "sqlite:///" + str(tmp_path / "s.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text)"))
        c.execute(text("insert into t values ('a')"))
    s = _env()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    ds = _create(s, 1, "dataset", "D", {
        "mode": "visual", "query": {"datasource_id": 1, "table": "t",
                                    "select": [{"column": "city"}],
                                    "limit": 100},
        "params": [], "sql": None, "auth": None}, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    app = _create(s, 1, "app", "T", {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [], "components": [
            {"id": "t", "type": "table", "dataset_id": ds.id,
             "limit": 10}]}]}, "admin", enabled=False)
    publish_asset(s, app.id, "admin")
    out = create_share(s, 1, app.id, "app", 1, "admin")
    data = public_data(s, out["token"])
    assert "sql" not in data["components"]["t"]
    import copy
    v = s.get(AssetVersion, app.published_version_id)
    content = copy.deepcopy(v.content_json)
    content["pages"][0]["components"][0]["dataset_id"] = 999
    v.content_json = content
    s.commit()
    s.expire_all()
    bad = public_data(s, out["token"])
    assert bad["components"]["t"]["error"] == "数据加载失败"
    assert "SQL" not in bad["components"]["t"]["error"]
