from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset, update_draft
from odf.db import Base
from odf.models import Datasource, LineageEdge, Project
from odf.services.catalog import impact, lineage
from odf.pipeline.lineage import _union_map
from odf.services.crypto import encrypt_secret


def _env(tmp_path):
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="l1", name="l1", status=1))
    src_url = "sqlite:///" + str(tmp_path / "src.db")
    dst_url = "sqlite:///" + str(tmp_path / "dst.db")
    with create_engine(src_url).begin() as c:
        c.execute(text("create table events (id int, name text, amount int)"))
    with create_engine(dst_url).begin() as c:
        c.execute(text("create table dest (id int, full_name text, amount int)"))
    s.add_all([
        Datasource(id=1, project_id=1, name="src", kind="sqlite",
                   dsn_encrypted=encrypt_secret(src_url)),
        Datasource(id=2, project_id=1, name="dst", kind="sqlite",
                   dsn_encrypted=encrypt_secret(dst_url)),
    ])
    s.commit()
    content = {
        "nodes": [
            {"id": "s", "type": "source",
             "config": {"datasource_id": 1, "table": "events", "pk": "id",
                        "cursor_column": "id"}},
            {"id": "r", "type": "rename",
             "config": {"mapping": {"name": "full_name"}}},
            {"id": "k", "type": "sink",
             "config": {"datasource_id": 2, "table": "dest",
                        "pk": ["id"], "mode": "upsert"}},
        ],
        "edges": [{"from": "s", "to": "r"}, {"from": "r", "to": "k"}],
        "settings": {},
    }
    a = create_asset(s, 1, "pipeline", "P", content, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    return s, a


def test_publish_records_column_lineage(tmp_path):
    s, a = _env(tmp_path)
    rows = s.query(LineageEdge).filter(
        LineageEdge.from_column.isnot(None)).all()
    pairs = {(r.from_ref, r.from_column, r.to_ref, r.to_column)
             for r in rows}
    assert ("1:events", "name", "2:dest", "full_name") in pairs
    assert ("1:events", "id", "2:dest", "id") in pairs
    assert ("1:events", "amount", "2:dest", "amount") in pairs
    out = lineage(s, 1)
    assert len(out["edges"]) == 2
    assert any(e["from_column"] == "name" and e["to_column"] == "full_name"
               for e in out["column_edges"])


def test_impact_walks_downstream_tables_and_columns(tmp_path):
    s, a = _env(tmp_path)
    out = impact(s, 1, "1:events")
    assert "2:dest" in out["nodes"]
    assert len(out["edges"]) == 2
    assert any(e["from_column"] == "name" and
               e["to_column"] == "full_name" for e in out["column_edges"])
    assert impact(s, 1, "2:dest")["edges"] == []


def test_republish_replaces_stale_column_edges(tmp_path):
    s, a = _env(tmp_path)
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "events", "pk": "id"}},
        {"id": "p", "type": "select",
         "config": {"columns": [{"column": "id"}]}},
        {"id": "k", "type": "sink",
         "config": {"datasource_id": 2, "table": "dest",
                    "pk": ["id"], "mode": "upsert"}}],
        "edges": [{"from": "s", "to": "p"}, {"from": "p", "to": "k"}],
        "settings": {}}
    update_draft(s, a.id, content, "admin")
    publish_asset(s, a.id, "admin")
    rows = s.query(LineageEdge).filter(
        LineageEdge.from_column.isnot(None)).all()
    assert {(r.from_column, r.to_column) for r in rows} == {("id", "id")}


def test_republish_is_idempotent(tmp_path):
    s, a = _env(tmp_path)
    publish_asset(s, a.id, "admin")
    rows = s.query(LineageEdge).filter(
        LineageEdge.from_column.isnot(None)).all()
    assert len(rows) == 3
