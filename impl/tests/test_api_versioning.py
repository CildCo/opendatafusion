import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.apistudio.content import empty_content
from odf.assets.service import (create_asset, publish_asset, rollback_asset,
                                update_draft)
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

VALID = {
    "mode": "visual",
    "query": {"datasource_id": 1, "table": "t",
              "select": [{"column": "id"}]},
    "sql": None, "params": [], "auth": {"type": "aksk",
                                        "rate_limit_per_min": 60},
}


@pytest.fixture()
def s(tmp_path):
    url = "sqlite:///" + str(tmp_path / "v.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    sess = sessionmaker(bind=e)()
    sess.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                        dsn_encrypted=encrypt_secret(url)))
    sess.commit()
    yield sess


def test_api_publish_validates_and_enables(s):
    a = create_asset(s, 1, "api", "A", VALID, "admin", enabled=False)
    v = publish_asset(s, a.id, "admin")
    s.refresh(a)
    assert v.status == "published"
    assert a.enabled is True


def test_api_publish_rejects_invalid_content(s):
    a = create_asset(s, 1, "api", "A", empty_content(), "admin",
                     enabled=False)
    with pytest.raises(ValueError):
        publish_asset(s, a.id, "admin")


def test_api_rollback_creates_new_published_version(s):
    a = create_asset(s, 1, "api", "A", VALID, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    update_draft(s, a.id, {**VALID, "params": [
        {"name": "x", "type": "number"}]}, "admin")
    publish_asset(s, a.id, "admin")
    rb = rollback_asset(s, a.id, 1, "admin")
    assert rb.version == 3 and rb.status == "published"
