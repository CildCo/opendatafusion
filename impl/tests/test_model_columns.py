import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.asset_lineage import asset_lineage
from odf.services.crypto import encrypt_secret
from odf.transform.content import validate_model


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "l.db")
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _content(sql, **extra):
    base = {"datasource_id": 1, "sql": sql, "materialization": "table",
            "schema": "main", "unique_key": [], "layer": "staging",
            "description": "", "tests": [], "columns": []}
    base.update(extra)
    return base


def test_column_definitions_validate_sources(tmp_path):
    s = _env(tmp_path)
    content = _content(
        "select 1", columns=[
            {"name": "city", "type": "varchar", "source": "base.city",
             "description": "City"},
            {"name": "total", "source": ""},
        ])
    assert validate_model(s, content, 1) == []
    bad = _content("select 1", columns=[{"name": "bad name"}])
    assert validate_model(s, bad, 1)
    bad_source = _content(
        "select 1", columns=[{"name": "a", "source": "a; drop table"}])
    assert validate_model(s, bad_source, 1)


def test_model_columns_produce_column_lineage(tmp_path):
    s = _env(tmp_path)
    base = create_asset(
        s, 1, "model", "base", _content(
            "select city, sum(amount) as total from orders group by city",
            columns=[{"name": "city"}, {"name": "total"}]), "admin")
    publish_asset(s, base.id, "admin")
    mart = create_asset(
        s, 1, "model", "mart", _content(
            "select city, total from {{ ref('%s') }}" % base.key,
            columns=[{"name": "city", "source": "city"},
                     {"name": "total", "source": "%s.total" % base.key}]),
        "admin")
    publish_asset(s, mart.id, "admin")
    graph = asset_lineage(s, 1, mart.id)
    edges = {(e["from_column"], e["to_column"])
             for e in graph["column_edges"]}
    assert ("city", "city") in edges
    assert ("total", "total") in edges
    assert all(e["to"] == "model:%d" % mart.id
               for e in graph["column_edges"])
    assert any(e["from"] == "model:%d" % base.id
               for e in graph["column_edges"])


def test_unknown_column_source_is_omitted(tmp_path):
    s = _env(tmp_path)
    base = create_asset(
        s, 1, "model", "base", _content(
            "select city from orders", columns=[{"name": "city"}]), "admin")
    publish_asset(s, base.id, "admin")
    mart = create_asset(
        s, 1, "model", "mart", _content(
            "select city from {{ ref('%s') }}" % base.key,
            columns=[{"name": "city", "source": "missing_col"}]), "admin")
    publish_asset(s, mart.id, "admin")
    graph = asset_lineage(s, 1, mart.id)
    assert graph["column_edges"] == []
