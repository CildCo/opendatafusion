import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Project
from odf.services.crypto import encrypt_secret
from odf.services.grants import (can_access, decide_request, list_grants,
                                 list_requests, request_access,
                                 request_by_key, revoke_grant, shared_asset,
                                 shared_assets)


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "g.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text)"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="a", name="A", status=1),
               Project(id=2, code="b", name="B", status=1)])
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    from odf.services.metadata import sync_datasource
    sync_datasource(s, 1)
    return s


def _dataset(s, name="orders", publish=True):
    asset = create_asset(
        s, 1, "dataset", name,
        {"mode": "visual",
         "query": {"datasource_id": 1, "table": "orders",
                   "select": [{"column": "id"}, {"column": "city"}],
                   "limit": 100},
         "params": [], "sql": None, "auth": None}, "admin")
    if publish:
        publish_asset(s, asset.id, "admin")
    return asset


def _model(s, name="m", publish=True):
    asset = create_asset(
        s, 1, "model", name,
        {"datasource_id": 1, "sql": "select 1", "materialization": "view",
         "schema": "main", "unique_key": [], "layer": "staging",
         "description": "", "tests": [], "columns": []}, "admin")
    if publish:
        publish_asset(s, asset.id, "admin")
    return asset


def test_request_approve_and_share_dataset(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    request = request_access(s, asset.id, 2, "bob", "need it")
    assert request["status"] == "pending"
    assert request["asset_type"] == "dataset"
    assert can_access(s, asset, 2) is False
    decided = decide_request(s, request["id"], 1, "alice", True)
    assert decided["status"] == "approved"
    assert can_access(s, asset, 2) is True
    shared = shared_assets(s, 2)
    assert [row["asset_id"] for row in shared] == [asset.id]
    detail = shared_asset(s, 2, asset.id)
    assert detail["asset_type"] == "dataset"
    assert {c["name"] for c in detail["columns"]} == {"id", "city"}
    grants = list_grants(s, 1, asset_type="dataset")
    assert grants[0]["grantee_project_id"] == 2
    revoke_grant(s, grants[0]["id"], 1, "alice")
    assert can_access(s, asset, 2) is False
    assert shared_assets(s, 2) == []


def test_request_by_key_and_model_metadata(tmp_path):
    s = _env(tmp_path)
    model = _model(s)
    request = request_by_key(s, model.key, 2, "bob")
    decide_request(s, request["id"], 1, "alice", True)
    detail = shared_asset(s, 2, model.id)
    assert detail["asset_type"] == "model"
    assert detail["layer"] == "staging"
    assert detail["target"]


def test_duplicate_and_self_requests_are_rejected(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    request_access(s, asset.id, 2, "bob")
    with pytest.raises(ValueError):
        request_access(s, asset.id, 2, "bob")
    with pytest.raises(ValueError):
        request_access(s, asset.id, 1, "alice")


def test_unpublished_and_unsupported_assets_are_rejected(tmp_path):
    s = _env(tmp_path)
    draft = _dataset(s, "draft", publish=False)
    with pytest.raises(ValueError):
        request_access(s, draft.id, 2, "bob")
    dashboard = create_asset(s, 1, "dashboard", "dash",
                             {"widgets": []}, "admin")
    publish_asset(s, dashboard.id, "admin")
    with pytest.raises(ValueError):
        request_access(s, dashboard.id, 2, "bob")


def test_pending_request_is_listed_for_both_sides(tmp_path):
    s = _env(tmp_path)
    asset = _dataset(s)
    request_access(s, asset.id, 2, "bob", "please")
    outgoing = list_requests(s, 2, "outgoing")
    incoming = list_requests(s, 1, "incoming")
    assert outgoing[0]["asset_name"] == "orders"
    assert incoming[0]["requested_by"] == "bob"


def test_datasets_and_models_can_be_requested_separately(tmp_path):
    s = _env(tmp_path)
    dataset = _dataset(s)
    model = _model(s)
    request_access(s, dataset.id, 2, "bob")
    request_access(s, model.id, 2, "bob")
    rows = list_requests(s, 2, "outgoing")
    assert {row["asset_type"] for row in rows} == {"dataset", "model"}
    assert len(rows) == 2
