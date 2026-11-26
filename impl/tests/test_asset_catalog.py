from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Job, Project
from odf.services.asset_catalog import (certify, list_assets, set_lifecycle,
                                        similar, trust)
from odf.services.governance import create_domain


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="default", name="Default", status=1))
    s.commit()
    return s


def _asset(s, name, type="dataset", owner="admin", domain_id=None):
    content = {"mode": "visual", "query": {"datasource_id": 1,
                                           "table": "t",
                                           "select": [{"column": "id"}],
                                           "limit": 100},
               "params": [], "sql": None, "auth": None}
    asset = create_asset(s, 1, type, name, content, owner, enabled=False)
    if domain_id is not None:
        asset.domain_id = domain_id
        s.commit()
    return asset


def test_trust_rewards_certification_and_usage():
    s = _env()
    d = create_domain(s, 1, "Sales", "")
    asset = _asset(s, "orders", domain_id=d.id)
    asset.contract_json = {"sla": "daily"}
    asset.owner = "admin"
    s.commit()
    before = trust(s, asset)
    assert before["score"] > 0
    assert any(f["key"] == "domain" and f["ok"] for f in before["factors"])
    certify(s, 1, asset.id, True, "approver", "reviewed")
    after = trust(s, asset)
    assert after["score"] > before["score"]
    assert after["level"] in ("good", "trusted")
    s.add(Job(project_id=1, asset_id=asset.id, asset_type="dataset",
              status="success"))
    s.commit()
    with_usage = trust(s, asset)
    assert with_usage["usage"]["runs"] == 1


def test_certification_and_lifecycle_validation():
    s = _env()
    asset = _asset(s, "orders")
    certify(s, 1, asset.id, True, "approver")
    s.refresh(asset)
    assert asset.certification == "certified"
    assert asset.certified_by == "approver"
    certify(s, 1, asset.id, False, "approver")
    s.refresh(asset)
    assert asset.certification == "none"
    set_lifecycle(s, 1, asset.id, "deprecated", "replaced", "approver")
    s.refresh(asset)
    assert asset.lifecycle == "deprecated"
    try:
        set_lifecycle(s, 1, asset.id, "gone", "", "approver")
    except ValueError as e:
        assert "lifecycle" in str(e)
    else:
        raise AssertionError("expected invalid lifecycle")


def test_search_ranks_certified_exact_match_first():
    s = _env()
    plain = _asset(s, "orders archive")
    exact = _asset(s, "orders")
    certify(s, 1, exact.id, True, "approver")
    out = list_assets(s, 1, q="orders", sort="relevance")
    names = [item["name"] for item in out["items"]]
    assert names.index("orders") < names.index("orders archive")
    assert out["items"][0]["certification"] == "certified"
    assert out["total"] >= 2


def test_lifecycle_filter_and_similar_assets():
    s = _env()
    d = create_domain(s, 1, "Sales", "")
    a = _asset(s, "orders", domain_id=d.id)
    b = _asset(s, "returns", domain_id=d.id)
    _asset(s, "old", domain_id=d.id)
    set_lifecycle(s, 1, b.id, "archived", "retired", "approver")
    active = list_assets(s, 1)
    assert "old" in [item["name"] for item in active["items"]]
    assert "returns" not in [item["name"] for item in active["items"]]
    archived = list_assets(s, 1, lifecycle="archived")
    assert [item["name"] for item in archived["items"]] == ["returns"]
    peers = similar(s, 1, a.id)
    assert peers
    assert peers[0]["name"] == "old"
    assert all(item["id"] != a.id for item in peers)
