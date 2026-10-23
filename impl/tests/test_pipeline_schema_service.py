import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Datasource
from odf.pipeline.schema_service import node_schemas
from odf.services.crypto import encrypt_secret


def test_source_and_transform_schema(tmp_path):
    url = "sqlite:///" + str(tmp_path / "s.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int, city text)"))
        c.execute(text("create table dst (id int, city text)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
        {"id": "f", "type": "filter", "config": {}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "f"}, {"from": "f", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    out = node_schemas(s, a.id)
    by = {n["node_id"]: n for n in out["nodes"]}
    assert [c["name"] for c in by["s"]["columns"]] == ["id", "city"]
    assert [c["name"] for c in by["o"]["columns"]] == ["id", "city"]


def test_schema_rejects_cross_project_datasource(tmp_path):
    url = "sqlite:///" + str(tmp_path / "x.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=2, name="other", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "src", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    with pytest.raises(ValueError):
        node_schemas(s, a.id)


def test_schema_reports_draft_source(tmp_path):
    url = "sqlite:///" + str(tmp_path / "d.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int)"))
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
         "config": {"datasource_id": 1, "table": "src", "pk": ["id"]}}],
        "edges": [{"from": "s", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    out = node_schemas(s, a.id)
    assert out["source"] == "draft"
    assert out["published"] is False


def test_schema_rejects_join_missing_key(tmp_path):
    url = "sqlite:///" + str(tmp_path / "j.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table a (id int)"))
        c.execute(text("create table b (id int)"))
        c.execute(text("create table o (id int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "a", "type": "source",
         "config": {"datasource_id": 1, "table": "a", "pk": "id"}},
        {"id": "b", "type": "source",
         "config": {"datasource_id": 1, "table": "b", "pk": "id"}},
        {"id": "j", "type": "join",
         "config": {"on": [{"left": "nope", "right": "id"}]}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "o", "pk": ["id"]}}],
        "edges": [{"from": "a", "to": "j", "to_port": "left"},
                  {"from": "b", "to": "j", "to_port": "right"},
                  {"from": "j", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    with pytest.raises(ValueError):
        node_schemas(s, a.id)


def test_schema_join_output(tmp_path):
    url = "sqlite:///" + str(tmp_path / "j2.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table a (id int, v text)"))
        c.execute(text("create table b (id int, w text)"))
        c.execute(text("create table o (id int, v text, w text)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {"nodes": [
        {"id": "a", "type": "source",
         "config": {"datasource_id": 1, "table": "a", "pk": "id"}},
        {"id": "b", "type": "source",
         "config": {"datasource_id": 1, "table": "b", "pk": "id"}},
        {"id": "j", "type": "join",
         "config": {"how": "inner",
                    "on": [{"left": "id", "right": "id"}]}},
        {"id": "o", "type": "sink",
         "config": {"datasource_id": 1, "table": "o", "pk": ["id"]}}],
        "edges": [{"from": "a", "to": "j", "to_port": "left"},
                  {"from": "b", "to": "j", "to_port": "right"},
                  {"from": "j", "to": "o"}]}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    out = node_schemas(s, a.id)
    by = {n["node_id"]: n for n in out["nodes"]}
    assert [c["name"] for c in by["j"]["columns"]] == ["id", "v", "w"]


def test_sink_missing_target_column_is_rejected(tmp_path):
    url = "sqlite:///" + str(tmp_path / "new.csv.db")
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
        node_schemas(s, a.id)
