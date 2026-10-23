import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import (create_asset, publish_asset, rollback_asset,
                                update_draft)
from odf.db import Base
from odf.models import AssetVersion

V1 = {"nodes": [
    {"id": "s", "type": "source", "config": {}},
    {"id": "o", "type": "sink", "config": {}}],
    "edges": [{"from": "s", "to": "o"}]}
V2 = {"nodes": [
    {"id": "s", "type": "source", "config": {}},
    {"id": "o", "type": "sink", "config": {}}],
    "edges": [{"from": "s", "to": "o"}], "settings": {"batch": 20}}


@pytest.fixture()
def s():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as sess:
        yield sess


def test_lifecycle(s):
    a = create_asset(s, 1, "widget", "P1", V1, "admin")
    assert a.draft_version_id == 1 and a.published_version_id is None
    assert publish_asset(s, a.id, "admin").version == 1
    v2 = update_draft(s, a.id, V2, "admin")
    assert v2.version == 2 and a.draft_version_id == 2
    pub = publish_asset(s, a.id, "admin")
    assert pub.version == 2 and a.published_version_id == 2
    rb = rollback_asset(s, a.id, 1, "admin")
    assert rb.version == 3 and rb.status == "published"
    assert rb.content_json == V1
    assert s.get(AssetVersion, 1).status == "archived"
    assert s.get(AssetVersion, 2).status == "archived"


def test_rollback_rejects_draft_version(s):
    a = create_asset(s, 1, "widget", "P1", V1, "admin")
    with pytest.raises(ValueError):
        rollback_asset(s, a.id, 1, "admin")


def test_publish_rejects_invalid_dag(s):
    a = create_asset(s, 1, "pipeline", "P1", {"nodes": [], "edges": []},
                     "admin")
    with pytest.raises(ValueError):
        publish_asset(s, a.id, "admin")


def test_create_asset_can_start_disabled(s):
    a = create_asset(s, 1, "api", "A", {"mode": "visual"}, "admin",
                     enabled=False)
    assert a.enabled is False
