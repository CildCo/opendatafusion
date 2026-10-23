from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import pytest

from odf.assets.service import (create_asset, publish_asset, rollback_asset,
                                update_draft)
from odf.db import Base
from odf.models import Datasource, LineageEdge
from odf.pipeline.validate import validate_pipeline_content
from odf.services.crypto import encrypt_secret


def test_publish_records_lineage_once(tmp_path):
    url = "sqlite:///" + str(tmp_path / "l.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
        c.execute(text("create table dst (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    publish_asset(s, a.id, "admin")
    publish_asset(s, a.id, "admin")
    edges = s.query(LineageEdge).filter_by(project_id=1).all()
    table_edges = [e for e in edges if e.from_column is None]
    assert len(table_edges) == 2
    assert {(e.from_type, e.to_type) for e in table_edges} == {
        ("table", "asset"), ("asset", "table")}
    column_edges = [e for e in edges if e.from_column is not None]
    assert len(column_edges) == 1
    assert column_edges[0].from_column == "id"
    assert column_edges[0].to_column == "id"


def test_publish_rejects_source_only_sink_kind(monkeypatch):
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="f", kind="file",
                     dsn_encrypted="x"))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "t", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    monkeypatch.setattr("odf.pipeline.validate.table_columns",
                        lambda *a, **k: ["id"])
    monkeypatch.setattr("odf.pipeline.schema_service.content_schemas",
                        lambda *a, **k: [])
    errs = validate_pipeline_content(s, content, 1)
    assert any("sink" in e["message"] and "supported" in e["message"]
               for e in errs)


def test_rollback_does_not_require_live_schema(tmp_path):
    url = "sqlite:///" + str(tmp_path / "rb.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "t", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    publish_asset(s, a.id, "admin")
    update_draft(s, a.id, {**content, "settings": {"batch": 10}}, "admin")
    publish_asset(s, a.id, "admin")
    with raw.begin() as c:
        c.execute(text("drop table t"))
    v = rollback_asset(s, a.id, 1, "admin")
    assert v.status == "published"


def test_publish_rejects_sink_schema_mismatch(tmp_path):
    url = "sqlite:///" + str(tmp_path / "bad.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int, v text)"))
        c.execute(text("create table dst (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    with pytest.raises(ValueError):
        publish_asset(s, a.id, "admin")
