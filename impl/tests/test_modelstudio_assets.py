import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Project
from odf.services.approval import issue_token
from odf.services.changes import apply, propose
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "limit": 100}, "params": [], "sql": None, "auth": None}
METRIC = {"dataset_id": None,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "format": {"type": "number"}}


@pytest.fixture()
def s(tmp_path):
    url = "sqlite:///" + str(tmp_path / "a.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    sess = sessionmaker(bind=e)()
    sess.add(Project(id=1, code="p", name="p", status=1))
    sess.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                        dsn_encrypted=encrypt_secret(url)))
    sess.commit()
    yield sess


def test_metric_publish_requires_published_dataset(s):
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    m = create_asset(s, 1, "metric", "M", {**METRIC, "dataset_id": d.id},
                     "admin", enabled=False)
    with pytest.raises(ValueError):
        publish_asset(s, m.id, "admin")
    publish_asset(s, d.id, "admin")
    v = publish_asset(s, m.id, "admin")
    assert v.status == "published"


def test_dataset_change_action_publishes(s):
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    c = propose(s, 1, "admin", "publish_dataset", d.id)
    apply(s, c.id, issue_token(d.id, "publish_dataset"))
    s.refresh(d)
    assert d.published_version_id is not None
