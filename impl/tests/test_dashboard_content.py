from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.dashboards.content import empty_dashboard, validate_dashboard
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "limit": 100}, "params": []}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "d.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _metric(s, ds_id):
    content = {"dataset_id": ds_id,
               "measure": {"agg": "sum", "column": "amount", "as": "value"},
               "dimensions": ["city"], "filters": [],
               "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", content, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return m.id


def test_empty_dashboard_is_valid_but_empty(tmp_path):
    s = _env(tmp_path)
    assert validate_dashboard(s, empty_dashboard(), 1) == []


def test_dashboard_widget_validation(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mid = _metric(s, ds.id)
    content = {"columns": 12, "row_height": 80, "widgets": [
        {"id": "w1", "type": "card", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2},
        {"id": "w2", "type": "line", "metric_id": mid,
         "dimension": "city", "x": 3, "y": 0, "w": 6, "h": 4},
        {"id": "w3", "type": "table", "dataset_id": ds.id,
         "x": 9, "y": 0, "w": 3, "h": 4},
        {"id": "w4", "type": "text", "text": "hello",
         "x": 0, "y": 2, "w": 3, "h": 2}]}
    assert validate_dashboard(s, content, 1) == []


def test_duplicate_and_out_of_bounds_are_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"columns": 12, "widgets": [
        {"id": "w1", "type": "text", "text": "a",
         "x": 0, "y": 0, "w": 8, "h": 1},
        {"id": "w1", "type": "text", "text": "b",
         "x": 8, "y": 0, "w": 8, "h": 1}]}
    errs = validate_dashboard(s, content, 1)
    assert any("id" in e["field"] for e in errs)
    assert any("x" in e["field"] or "bounds" in e["field"] for e in errs)


def test_chart_requires_metric_dimension(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mid = _metric(s, ds.id)
    content = {"widgets": [
        {"id": "w", "type": "line", "metric_id": mid,
         "x": 0, "y": 0, "w": 6, "h": 4}]}
    assert validate_dashboard(s, content, 1)


def test_dataset_table_limit_is_validated(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    content = {"widgets": [
        {"id": "t", "type": "table", "dataset_id": ds.id, "limit": 0,
         "x": 0, "y": 0, "w": 3, "h": 2}]}
    assert any("limit" in e["field"] for e in
               validate_dashboard(s, content, 1))


def test_malformed_ids_and_table_targets_are_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"widgets": [
        {"id": "a", "type": "card", "metric_id": [1],
         "x": 0, "y": 0, "w": 3, "h": 2},
        {"id": "b", "type": "table", "dataset_id": 1, "metric_id": 2,
         "x": 3, "y": 0, "w": 3, "h": 2}]}
    errs = validate_dashboard(s, content, 1)
    assert any(e["field"] == "metric_id" for e in errs)
    assert any("dataset or a metric" in e["message"] for e in errs)


def test_non_integer_grid_is_rejected(tmp_path):
    s = _env(tmp_path)
    assert validate_dashboard(s, {"columns": "12", "widgets": []}, 1)
    assert validate_dashboard(s, {"row_height": True, "widgets": []}, 1)


def test_dashboard_params_filters_and_emit(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mid = _metric(s, ds.id)
    content = {"params": [{"name": "city", "type": "string"}], "widgets": [
        {"id": "w", "type": "bar", "metric_id": mid, "dimension": "city",
         "x": 0, "y": 0, "w": 6, "h": 4,
         "filters": [{"column": "city", "op": "=", "param": "city"}],
         "emit": {"param": "city", "from": "city"}}]}
    assert validate_dashboard(s, content, 1) == []


def test_undeclared_param_unknown_column_and_bad_emit(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mid = _metric(s, ds.id)
    content = {"widgets": [
        {"id": "a", "type": "card", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "nope", "op": "=", "param": "city"}]},
        {"id": "b", "type": "table", "dataset_id": ds.id,
         "x": 3, "y": 0, "w": 3, "h": 2,
         "emit": {"param": "missing", "from": "city"}},
        {"id": "c", "type": "text", "text": "x",
         "x": 6, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "city", "op": "=", "param": "city"}]}]}
    errs = validate_dashboard(s, content, 1)
    assert any("nope" in e["message"] for e in errs)
    assert any("not declared" in e["message"] for e in errs)
    assert any("text" in e["field"] for e in errs)


def test_metric_table_emit_is_validated(tmp_path):
    s = _env(tmp_path)
    ds = create_asset(s, 1, "dataset", "D", DATASET, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    mid = _metric(s, ds.id)
    ok = {"params": [{"name": "city", "type": "string"}], "widgets": [
        {"id": "t", "type": "table", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "emit": {"param": "city", "from": "city"}}]}
    assert validate_dashboard(s, ok, 1) == []
    bad = {"widgets": [
        {"id": "t", "type": "table", "metric_id": mid,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "emit": {"param": "NOPE", "from": "NO_COLUMN"}}]}
    assert validate_dashboard(s, bad, 1)


def test_dataset_filter_uses_source_columns_not_aliases(tmp_path):
    s = _env(tmp_path)
    aliased = {**DATASET, "query": {**DATASET["query"], "select": [
        {"column": "city", "as": "town"}, {"column": "amount"}]}}
    ds = create_asset(s, 1, "dataset", "D", aliased, "admin", enabled=False)
    publish_asset(s, ds.id, "admin")
    good = {"params": [{"name": "city", "type": "string"}], "widgets": [
        {"id": "t", "type": "table", "dataset_id": ds.id,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "city", "op": "=", "param": "city"}]}]}
    assert validate_dashboard(s, good, 1) == []
    bad = {"params": [{"name": "city", "type": "string"}], "widgets": [
        {"id": "t", "type": "table", "dataset_id": ds.id,
         "x": 0, "y": 0, "w": 3, "h": 2,
         "filters": [{"column": "town", "op": "=", "param": "city"}]}]}
    assert validate_dashboard(s, bad, 1)


def test_non_list_params_do_not_raise(tmp_path):
    s = _env(tmp_path)
    errs = validate_dashboard(
        s, {"params": 5, "widgets": [
            {"id": "t", "type": "text", "text": "x",
             "x": 0, "y": 0, "w": 3, "h": 2}]}, 1)
    assert errs


def test_blank_non_string_default_is_no_default(tmp_path):
    s = _env(tmp_path)
    content = {"params": [{"name": "n", "type": "number", "default": ""}],
               "widgets": [{"id": "t", "type": "text", "text": "x",
                            "x": 0, "y": 0, "w": 3, "h": 2}]}
    assert validate_dashboard(s, content, 1) == []
