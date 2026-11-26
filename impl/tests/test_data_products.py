from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Project
from odf.products.content import empty_product, product_bundle, validate_product


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.add(Project(id=2, code="q", name="Q", status=1))
    s.commit()
    return s


def test_product_validation_and_publish():
    s = _env()
    a = create_asset(s, 1, "dashboard", "Board", {"widgets": []}, "admin",
                     enabled=False)
    p = create_asset(s, 1, "data_product", "Product",
                     {"summary": "Bundle", "owner": "alice", "sla": "daily",
                      "asset_ids": [a.id], "terms": ["sales"]},
                     "admin", enabled=False)
    publish_asset(s, p.id, "admin")
    assert p.published_version_id
    bad = {**empty_product(), "asset_ids": [999]}
    assert validate_product(s, bad, 1)
    bad = {**empty_product(), "asset_ids": [a.id], "summary": "x" * 5000}
    assert any(e["field"] == "summary" for e in validate_product(s, bad, 1))


def test_product_cannot_reference_other_project_or_product():
    s = _env()
    other = create_asset(s, 2, "dashboard", "Other", {"widgets": []}, "u")
    inner = create_asset(s, 1, "data_product", "Inner",
                         {**empty_product(), "asset_ids": [other.id]}, "u")
    content = {**empty_product(), "asset_ids": [other.id]}
    assert any("asset not found" in e["message"]
               for e in validate_product(s, content, 1))
    content = {**empty_product(), "asset_ids": [inner.id]}
    assert any("other products" in e["message"]
               for e in validate_product(s, content, 1))


def test_product_bundle_carries_product_metadata():
    s = _env()
    a = create_asset(s, 1, "dashboard", "Board", {"widgets": []}, "admin",
                     enabled=False)
    content = {"summary": "Bundle", "owner": "alice", "sla": "daily",
               "asset_ids": [a.id], "terms": ["sales"]}
    p = create_asset(s, 1, "data_product", "Product", content, "admin",
                     enabled=False)
    publish_asset(s, p.id, "admin")
    bundle = product_bundle(s, 1, content)
    assert bundle["product"]["owner"] == "alice"
    assert bundle["format"] == "odf-bundle"
