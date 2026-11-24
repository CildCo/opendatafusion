from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.modelstudio.content import (metric_dimensions, validate_metric)
from odf.modelstudio.service import query_metric
from odf.modelstudio.timegrain import bucket_sql, shift_time
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "order_date"}, {"column": "city"},
               {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "g.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (order_date text, city text, "
                       "amount int)"))
        c.execute(text(
            "insert into t values "
            "('2025-12-20','a',4),('2026-01-15','a',10),"
            "('2026-01-20','b',5),('2026-02-03','a',7)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _metric(s, time, compare="none", filters=None):
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    content = {"dataset_id": d.id,
               "measure": {"agg": "sum", "column": "amount",
                           "as": "value"},
               "dimensions": [], "filters": filters or [],
               "time": time, "compare": compare,
               "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", content, "admin", enabled=False)
    return m, content


def test_metric_groups_by_month(tmp_path):
    s = _env(tmp_path)
    m, _ = _metric(s, {"column": "order_date", "grain": "month"})
    out = query_metric(s, m.id)
    rows = sorted(out["rows"], key=lambda r: r["order_date"])
    assert rows == [{"order_date": "2025-12-01", "value": 4},
                    {"order_date": "2026-01-01", "value": 15},
                    {"order_date": "2026-02-01", "value": 7}]


def test_metric_time_column_is_a_dimension():
    content = {"dimensions": ["city"],
               "time": {"column": "order_date", "grain": "month"}}
    assert metric_dimensions(content) == ["city", "order_date"]


def test_metric_previous_period_aligns_buckets(tmp_path):
    s = _env(tmp_path)
    m, _ = _metric(s, {"column": "order_date", "grain": "month"},
                   compare="previous")
    out = query_metric(s, m.id, compare="previous")
    rows = {r["order_date"]: r for r in out["rows"]}
    assert rows["2026-01-01"]["value"] == 15
    assert rows["2026-01-01"]["value_previous"] == 4
    assert rows["2026-02-01"]["value_previous"] == 15
    assert rows["2026-02-01"]["value_delta"] == -8
    assert rows["2026-02-01"]["value_delta_pct"] == -53.33


def test_metric_previous_period_shifts_date_filters(tmp_path):
    s = _env(tmp_path)
    m, _ = _metric(
        s, {"column": "order_date", "grain": "month"},
        compare="previous",
        filters=[{"column": "order_date", "op": ">=",
                  "value": "2026-01-01"}])
    out = query_metric(s, m.id, compare="previous")
    rows = {r["order_date"]: r for r in out["rows"]}
    assert set(rows) == {"2026-01-01", "2026-02-01"}
    assert rows["2026-01-01"]["value_previous"] == 4
    assert rows["2026-02-01"]["value_previous"] == 15


def test_metric_year_comparison(tmp_path):
    s = _env(tmp_path)
    m, _ = _metric(s, {"column": "order_date", "grain": "month"},
                   compare="year")
    out = query_metric(s, m.id, compare="year")
    assert out["columns"][-1] == "value_delta_pct"
    assert all(r["value_previous"] is None for r in out["rows"])


def test_metric_time_validation(tmp_path):
    s = _env(tmp_path)
    d = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, d.id, "admin")
    base = {"dataset_id": d.id,
            "measure": {"agg": "sum", "column": "amount", "as": "value"},
            "dimensions": [], "filters": [], "format": {"type": "number"}}
    assert validate_metric(s, {**base, "time": {"column": "nope",
                                                "grain": "month"}}, 1)
    assert validate_metric(s, {**base, "time": {"column": "order_date",
                                                "grain": "week2"}}, 1)
    assert validate_metric(s, {**base, "dimensions": ["order_date"],
                               "time": {"column": "order_date",
                                        "grain": "month"}}, 1)
    assert validate_metric(s, {**base, "compare": "previous"}, 1)
    assert validate_metric(s, {**base, "compare": "sometimes"}, 1) == [
        {"field": "compare",
         "message": "compare must be none, previous or year"}]
    assert validate_metric(s, {**base,
                               "time": {"column": "order_date",
                                        "grain": "month"},
                               "compare": "previous"}, 1) == []


def test_bucket_sql_dialects():
    assert bucket_sql("sqlite", '"d"', "month") == \
        "date(\"d\", 'start of month')"
    assert bucket_sql("postgres", '"d"', "month") == \
        "date_trunc('month', \"d\")"
    assert bucket_sql("oracle", '"d"', "quarter") == "TRUNC(\"d\", 'Q')"
    assert bucket_sql("mysql", '"d"', "year") == \
        "DATE_FORMAT(\"d\", '%Y-01-01')"


def test_shift_time_units():
    assert shift_time("2026-01-31", "month", -1) == "2025-12-31"
    assert shift_time("2026-01-15", "year", 1) == "2027-01-15"
    assert shift_time("2026-01-15", "day", -1) == "2026-01-14"
