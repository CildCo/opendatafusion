import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import AssetVersion, Job
from odf.services.jobs import scheduler_tick

CONTENT = {"nodes": [
    {"id": "s", "type": "source", "config": {}},
    {"id": "o", "type": "sink", "config": {}}],
    "edges": [{"from": "s", "to": "o"}]}


@pytest.fixture()
def s():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as sess:
        yield sess


def test_scheduler_enqueues_pipeline(s):
    a = create_asset(s, 1, "pipeline", "p", CONTENT, "admin")
    v = s.get(AssetVersion, a.draft_version_id)
    v.status = "published"
    a.published_version_id = v.id
    a.cron = "0 */5 * * * ?"
    a.enabled = True
    s.commit()
    scheduler_tick(s)
    assert s.query(Job).filter_by(asset_id=a.id,
                                  asset_type="pipeline").count() == 1
    scheduler_tick(s)
    assert s.query(Job).filter_by(asset_id=a.id,
                                  asset_type="pipeline").count() == 1


def test_scheduler_skips_unpublished_pipeline(s):
    a = create_asset(s, 1, "pipeline", "p", CONTENT, "admin")
    a.cron = "0 */5 * * * ?"
    a.enabled = True
    s.commit()
    scheduler_tick(s)
    assert s.query(Job).filter_by(asset_id=a.id,
                                  asset_type="pipeline").count() == 0
