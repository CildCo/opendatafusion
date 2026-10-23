from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.apistudio.service import run_content
from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource, Project
from odf.modelstudio.service import preview_dataset, query_metric
from odf.services.crypto import encrypt_secret
from odf.services.masking import create_column_policy, mask_value
from odf.services.metadata import sync_datasource


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "m.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table people (id int, email text, phone text)"))
        c.execute(text("insert into people values "
                       "(1,'alice@example.com','13800138000'),"
                       "(2,'bob@example.com','13900139000')"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="m1", name="m1", status=1))
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    sync_datasource(s, 1)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "people",
                         "select": [{"column": "id"},
                                    {"column": "email", "as": "contact"},
                                    {"column": "phone"}],
                         "limit": 100},
               "params": [], "sql": None, "auth": None}
    a = create_asset(s, 1, "dataset", "D", content, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    create_column_policy(s, 1, a.id, "email", "pii", "redact", ["editor"],
                        "admin")
    create_column_policy(s, 1, a.id, "phone", "pii", "partial", [], "admin")
    return s, a


def test_dataset_preview_masks_by_role(tmp_path):
    s, a = _env(tmp_path)
    viewer = preview_dataset(s, a.id, published_only=True, role="viewer")
    assert viewer["rows"][0]["contact"] == "***"
    assert viewer["rows"][0]["phone"] == "13*******00"
    editor = preview_dataset(s, a.id, published_only=True, role="editor")
    assert editor["rows"][0]["contact"] == "alice@example.com"
    assert editor["rows"][0]["phone"] == "13*******00"
    admin = preview_dataset(s, a.id, published_only=True, role="admin")
    assert admin["rows"][0]["phone"] == "13800138000"


def test_metric_dimension_is_masked(tmp_path):
    s, a = _env(tmp_path)
    metric = {"dataset_id": a.id,
              "measure": {"agg": "count", "column": "*", "as": "value"},
              "dimensions": ["contact"], "filters": [],
              "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", metric, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    out = query_metric(s, m.id, role="viewer")
    assert out["rows"][0]["contact"] == "***"
    assert query_metric(s, m.id, role="editor")["rows"][0]["contact"] == \
        "alice@example.com"


def test_visual_api_masks_external_callers(tmp_path):
    s, a = _env(tmp_path)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "people",
                         "select": [{"column": "email", "as": "contact"}],
                         "limit": 100},
               "params": [], "sql": None,
               "auth": {"type": "aksk", "rate_limit_per_min": 60}}
    api = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    publish_asset(s, api.id, "admin")
    out = run_content(s, api, content, {}, role="viewer")
    assert out["rows"][0]["contact"] == "***"
    raw = run_content(s, api, content, {}, role="editor")
    assert raw["rows"][0]["contact"] == "alice@example.com"


def test_mask_value_modes():
    assert mask_value("abcdef", "partial") == "a****f"
    assert mask_value(123456789, "redact") == "***"
    assert mask_value("x", "null") is None
    assert mask_value("alice@example.com", "hash").startswith("sha256:")


def test_governed_datasource_blocks_raw_sql_paths(tmp_path):
    import pytest
    from odf.apistudio.content import validate_content
    from odf.workbench.service import run_query
    s, _ = _env(tmp_path)
    sql_content = {"mode": "sql", "query": {"datasource_id": 1},
                   "sql": "select * from people", "params": []}
    errs = validate_content(s, sql_content, 1)
    assert any("governed" in e["message"] for e in errs)
    with pytest.raises(ValueError):
        run_query(s, 1, 1, "select * from people", role="viewer")
    assert run_query(s, 1, 1, "select count(*) as n from people",
                     role="admin")["rows"] == [{"n": 2}]


def test_metric_measure_on_aliased_sensitive_column_is_masked(tmp_path):
    s, a = _env(tmp_path)
    metric = {"dataset_id": a.id,
              "measure": {"agg": "min", "column": "contact",
                          "as": "first_contact"},
              "dimensions": [], "filters": [],
              "format": {"type": "text"}}
    m = create_asset(s, 1, "metric", "M2", metric, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    out = query_metric(s, m.id, role="viewer")
    assert out["rows"][0]["first_contact"] == "***"
    assert query_metric(s, m.id, role="admin")["rows"][0]["first_contact"] == \
        "alice@example.com"
