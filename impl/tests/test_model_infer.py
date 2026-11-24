import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret
from odf.transform.lineage import infer_columns


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "i.db")
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _model(s, name, sql, columns=None):
    return create_asset(
        s, 1, "model", name,
        {"datasource_id": 1, "sql": sql, "materialization": "table",
         "schema": "main", "unique_key": [], "layer": "staging",
         "description": "", "tests": [], "columns": columns or []},
        "admin")


def test_direct_projection_uses_ref_key(tmp_path):
    s = _env(tmp_path)
    base = _model(s, "base", "select city, sum(amount) as total "
                             "from orders group by city")
    publish_asset(s, base.id, "admin")
    mart = _model(s, "mart", "select city, total as revenue "
                             "from {{ ref('%s') }}" % base.key)
    columns = infer_columns(s, mart, mart_content(s, mart))
    by_name = {c["name"]: c for c in columns}
    assert by_name["city"]["source"] == "%s.city" % base.key
    assert by_name["revenue"]["source"] == "%s.total" % base.key


def mart_content(s, asset):
    from odf.models import AssetVersion
    return s.get(AssetVersion, asset.draft_version_id).content_json


def test_expression_keeps_referenced_column(tmp_path):
    s = _env(tmp_path)
    base = _model(s, "base", "select city from orders")
    publish_asset(s, base.id, "admin")
    mart = _model(s, "upper", "select upper(city) as city_upper "
                              "from {{ ref('%s') }}" % base.key)
    columns = infer_columns(s, mart, mart_content(s, mart))
    assert columns[0]["source"] == "%s.city" % base.key


def test_multi_column_expression_has_no_source(tmp_path):
    s = _env(tmp_path)
    base = _model(s, "base", "select city, amount from orders")
    publish_asset(s, base.id, "admin")
    mart = _model(s, "label", "select city || amount as label "
                              "from {{ ref('%s') }}" % base.key)
    columns = infer_columns(s, mart, mart_content(s, mart))
    assert columns[0]["source"] == ""


def test_join_uses_table_alias(tmp_path):
    s = _env(tmp_path)
    base = _model(s, "base", "select city from orders")
    other = _model(s, "other", "select code from codes")
    publish_asset(s, base.id, "admin")
    publish_asset(s, other.id, "admin")
    mart = _model(
        s, "joined",
        "select b.city, o.code from {{ ref('%s') }} b "
        "join {{ ref('%s') }} o on b.city = o.code" % (base.key,
                                                        other.key))
    columns = infer_columns(s, mart, mart_content(s, mart))
    by_name = {c["name"]: c for c in columns}
    assert by_name["city"]["source"] == "%s.city" % base.key
    assert by_name["code"]["source"] == "%s.code" % other.key


def test_manual_sources_are_preserved(tmp_path):
    s = _env(tmp_path)
    base = _model(s, "base", "select city from orders")
    publish_asset(s, base.id, "admin")
    mart = _model(
        s, "manual", "select city from {{ ref('%s') }}" % base.key,
        columns=[{"name": "city", "source": "custom.city",
                  "description": "kept"}])
    columns = infer_columns(s, mart, mart_content(s, mart))
    assert columns[0]["source"] == "custom.city"


def test_unparseable_sql_raises(tmp_path):
    s = _env(tmp_path)
    base = _model(s, "base", "select city from orders")
    publish_asset(s, base.id, "admin")
    mart = _model(s, "bad", "select from where {{ ref('%s') }}" % base.key)
    with pytest.raises(ValueError):
        infer_columns(s, mart, mart_content(s, mart))
