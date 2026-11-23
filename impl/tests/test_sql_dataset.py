from pathlib import Path

from sqlalchemy import create_engine, text

from odf.assets.service import create_asset, publish_asset, update_draft
from odf.models import Datasource, Project
from odf.services.crypto import encrypt_secret
from odf.db import Base
from sqlalchemy.orm import sessionmaker


def _session(tmp_path):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Project(id=1, code="p", name="P", status=1))
    path = tmp_path / "sql_dataset.db"
    raw = create_engine("sqlite:///%s" % path.as_posix())
    with raw.begin() as c:
        c.execute(text("create table orders (id int, region text, amount int)"))
        c.execute(text("create table regions (name text, manager text)"))
        c.execute(text("insert into orders values (1,'east',10),(2,'west',20)"))
        c.execute(text("insert into regions values ('east','A'),('west','B')"))
    raw.dispose()
    ds = Datasource(project_id=1, name="sqlite", kind="sqlite",
                    dsn_encrypted=encrypt_secret(
                        "sqlite:///%s" % path.as_posix()))
    s.add(ds)
    s.commit()
    return s, ds


def test_sql_dataset_joins_and_derives_columns(tmp_path):
    from odf.modelstudio.service import dataset_schema, query_metric
    s, ds = _session(tmp_path)
    content = {"mode": "sql",
               "query": {"datasource_id": ds.id},
               "sql": "select o.id, o.region, o.amount, r.manager "
                      "from orders o join regions r on r.name = o.region",
               "params": [], "auth": None}
    dataset = create_asset(s, 1, "dataset", "SQL DS", content, "u")
    update_draft(s, dataset.id, content, "u", base_version=1)
    publish_asset(s, dataset.id, "u")
    s.refresh(dataset)
    schema = dataset_schema(s, dataset.id)
    assert [c["name"] for c in schema["columns"]] == [
        "id", "region", "amount", "manager"]

    metric_content = {
        "dataset_id": dataset.id,
        "measure": {"agg": "sum", "column": "amount", "as": "total"},
        "dimensions": ["region"], "filters": [],
        "format": {"type": "number"},
    }
    metric = create_asset(s, 1, "metric", "M", metric_content, "u")
    publish_asset(s, metric.id, "u")
    out = query_metric(s, metric.id, limit=10)
    assert out["row_count"] == 2
    assert sum(row["total"] for row in out["rows"]) == 30

    distinct_content = {
        "dataset_id": dataset.id,
        "measure": {"agg": "count_distinct", "column": "region",
                    "as": "regions"},
        "dimensions": [], "filters": [],
        "format": {"type": "number"},
    }
    distinct = create_asset(s, 1, "metric", "D", distinct_content, "u")
    publish_asset(s, distinct.id, "u")
    assert query_metric(s, distinct.id, limit=10)["rows"][0]["regions"] == 2
