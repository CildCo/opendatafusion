import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.connectors.sql import SQLSink
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "s.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table target (id int primary key, v text)"))
        c.execute(text("insert into target values (1,'old'),(2,'keep')"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s, raw


def _rows(url):
    raw = create_engine(url)
    with raw.connect() as c:
        rows = [dict(r) for r in c.execute(
            text("select id, v from target order by id")).mappings()]
    raw.dispose()
    return rows


def test_cdc_sink_deletes_and_upserts(tmp_path):
    s, _ = _env(tmp_path)
    ds = s.get(Datasource, 1)
    sink = SQLSink(ds, {"sink_table": "target", "pk": ["id"],
                        "mode": "cdc"})
    sink.write([
        {"id": 1, "v": "gone", "__odf_op": "delete"},
        {"id": 2, "v": "new", "__odf_op": "upsert"},
        {"id": 3, "v": "added", "__odf_op": "upsert"},
    ])
    rows = _rows("sqlite:///" + str(tmp_path / "s.db"))
    assert rows == [{"id": 2, "v": "new"}, {"id": 3, "v": "added"}]


def test_cdc_sink_requires_primary_key(tmp_path):
    s, _ = _env(tmp_path)
    ds = s.get(Datasource, 1)
    sink = SQLSink(ds, {"sink_table": "target", "pk": ["id"],
                        "mode": "cdc"})
    sink.write([{"id": 9, "v": "x"}])
    assert {"id": 9, "v": "x"} in _rows("sqlite:///" + str(tmp_path / "s.db"))


def test_unsupported_mode_is_rejected(tmp_path):
    s, _ = _env(tmp_path)
    ds = s.get(Datasource, 1)
    sink = SQLSink(ds, {"sink_table": "target", "pk": ["id"],
                        "mode": "merge"})
    with pytest.raises(ValueError):
        sink.write([{"id": 1, "v": "x"}])


def _columns(url, table):
    raw = create_engine(url)
    with raw.connect() as c:
        cols = [row[1] for row in c.execute(text(
            "pragma table_info(%s)" % table))]
    raw.dispose()
    return cols


def test_sink_evolves_new_columns(tmp_path):
    s, _ = _env(tmp_path)
    ds = s.get(Datasource, 1)
    sink = SQLSink(ds, {"sink_table": "target", "pk": ["id"],
                        "mode": "cdc", "evolve": True})
    sink.write([{"id": 4, "v": "x", "extra": "note", "__odf_op": "upsert"}])
    url = "sqlite:///" + str(tmp_path / "s.db")
    assert "extra" in _columns(url, "target")
    rows = _rows(url)
    assert {"id": 4, "v": "x"} in [{"id": r["id"], "v": r["v"]} for r in rows]


def test_sink_without_evolve_ignores_new_columns(tmp_path):
    s, _ = _env(tmp_path)
    ds = s.get(Datasource, 1)
    sink = SQLSink(ds, {"sink_table": "target", "pk": ["id"],
                        "mode": "upsert"})
    sink.write([{"id": 4, "v": "x", "extra": "note"}])
    url = "sqlite:///" + str(tmp_path / "s.db")
    assert "extra" not in _columns(url, "target")
