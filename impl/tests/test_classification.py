from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import ColumnPolicy, Datasource
from odf.services.classification import propagate_model_policies
from odf.services.crypto import encrypt_secret
from odf.services.masking import create_column_policy
from odf.services.metadata import sync_datasource
from odf.transform.service import sync_model_graph


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "cl.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text, amount int)"))
        c.execute(text("insert into orders values (1,'a',10)"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    sync_datasource(s, 1)
    return s


def _dataset(s):
    return create_asset(
        s, 1, "dataset", "orders",
        {"mode": "visual",
         "query": {"datasource_id": 1, "table": "orders",
                   "select": [{"column": "id"}, {"column": "city"},
                              {"column": "amount"}], "limit": 100},
         "params": [], "sql": None, "auth": None}, "admin")


def _model(s, name, sql, columns):
    return create_asset(
        s, 1, "model", name,
        {"datasource_id": 1, "sql": sql, "materialization": "table",
         "schema": "main", "unique_key": [], "layer": "staging",
         "description": "", "tests": [], "columns": columns},
        "admin")


def _policy(s, table, column):
    return (s.query(ColumnPolicy)
            .filter_by(datasource_id=1, schema_name="main",
                       table_name=table, column_name=column).first())


def test_policy_propagates_from_source_table(tmp_path):
    s = _env(tmp_path)
    dataset = _dataset(s)
    publish_asset(s, dataset.id, "admin")
    create_column_policy(s, 1, dataset.id, "city", "pii", "partial", [],
                         "admin")
    base = _model(s, "base", "select city, amount from orders",
                  [{"name": "city", "source": "city"},
                   {"name": "amount", "source": "amount"}])
    publish_asset(s, base.id, "admin")
    sync_model_graph(s, base, _content(s, base))
    row = _policy(s, base.key, "city")
    assert row is not None
    assert row.classification == "pii"
    assert row.mask_type == "partial"
    assert row.source == "lineage"
    assert _policy(s, base.key, "amount") is None


def test_policy_propagates_between_models(tmp_path):
    s = _env(tmp_path)
    dataset = _dataset(s)
    publish_asset(s, dataset.id, "admin")
    create_column_policy(s, 1, dataset.id, "city", "pii", "redact", [],
                         "admin")
    base = _model(s, "base", "select city from orders",
                  [{"name": "city", "source": "city"}])
    publish_asset(s, base.id, "admin")
    sync_model_graph(s, base, _content(s, base))
    mart = _model(
        s, "mart", "select city from {{ ref('%s') }}" % base.key,
        [{"name": "city", "source": "%s.city" % base.key}])
    publish_asset(s, mart.id, "admin")
    sync_model_graph(s, mart, _content(s, mart))
    row = _policy(s, mart.key, "city")
    assert row is not None and row.classification == "pii"


def test_manual_policy_is_not_overwritten(tmp_path):
    s = _env(tmp_path)
    dataset = _dataset(s)
    publish_asset(s, dataset.id, "admin")
    create_column_policy(s, 1, dataset.id, "city", "pii", "redact", [],
                         "admin")
    base = _model(s, "base", "select city from orders",
                  [{"name": "city", "source": "city"}])
    publish_asset(s, base.id, "admin")
    manual = ColumnPolicy(project_id=1, datasource_id=1,
                          schema_name="main", table_name=base.key,
                          column_name="city", classification="sensitive",
                          mask_type="hash", exempt_roles_json=[],
                          source="manual", created_by="admin")
    s.add(manual)
    s.commit()
    sync_model_graph(s, base, _content(s, base))
    row = _policy(s, base.key, "city")
    assert row.classification == "sensitive"
    assert row.source == "manual"


def test_removed_column_policy_is_cleaned(tmp_path):
    s = _env(tmp_path)
    dataset = _dataset(s)
    publish_asset(s, dataset.id, "admin")
    create_column_policy(s, 1, dataset.id, "city", "pii", "redact", [],
                         "admin")
    base = _model(s, "base", "select city, amount from orders",
                  [{"name": "city", "source": "city"},
                   {"name": "amount", "source": "amount"}])
    publish_asset(s, base.id, "admin")
    sync_model_graph(s, base, _content(s, base))
    assert _policy(s, base.key, "city") is not None
    reduced = dict(_content(s, base))
    reduced["columns"] = [{"name": "amount", "source": "amount"}]
    propagate_model_policies(s, base, reduced)
    s.commit()
    assert _policy(s, base.key, "city") is None
    assert _policy(s, base.key, "amount") is None


def _content(s, asset):
    from odf.models import AssetVersion
    return s.get(AssetVersion, asset.published_version_id).content_json
