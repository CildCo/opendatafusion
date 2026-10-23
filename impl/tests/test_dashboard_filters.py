from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.modelstudio.service import preview_dataset, query_metric
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "f.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
        c.execute(text("insert into t values ('a',10),('a',5),('b',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _models(s):
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mc = {"dataset_id": ds.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return ds.id, m.id


def test_metric_and_dataset_extra_filters(tmp_path):
    s = _env(tmp_path)
    dsid, mid = _models(s)
    r = query_metric(s, mid, limit=10,
                     extra_filters=[{"column": "city", "op": "=",
                                     "value": "a"}])
    assert [(x["city"], x["value"]) for x in r["rows"]] == [("a", 15)]
    d = preview_dataset(s, dsid, limit=10,
                        extra_filters=[{"column": "amount", "op": ">",
                                        "value": 6}])
    assert d["row_count"] == 2
