import time
from types import SimpleNamespace

from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, func, select

from odf.connectors.sql import SQLSink
from odf.services.crypto import encrypt_secret


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "sink.db")
    e = create_engine(url)
    md = MetaData()
    t = Table("t", md, Column("id", Integer, primary_key=True),
              Column("v", String))
    md.create_all(e)
    ds = SimpleNamespace(kind="sqlite", dsn_encrypted=encrypt_secret(url),
                         id=1, project_id=1)
    return e, t, ds


def test_bulk_upsert_is_fast_and_correct(tmp_path):
    e, t, ds = _env(tmp_path)
    rows = [{"id": i, "v": "x"} for i in range(1, 5001)]
    started = time.perf_counter()
    SQLSink(ds, {"sink_table": "t", "pk": ["id"],
                 "mode": "upsert"}).write(rows)
    elapsed = time.perf_counter() - started
    assert elapsed < 0.8, f"bulk upsert took {elapsed:.2f}s"
    with e.connect() as c:
        assert c.execute(select(func.count()).select_from(t)).scalar() == 5000
    changed = [{"id": 1, "v": "updated"}]
    SQLSink(ds, {"sink_table": "t", "pk": ["id"],
                 "mode": "upsert"}).write(changed)
    with e.connect() as c:
        assert c.execute(select(t.c.v).where(t.c.id == 1)).scalar() == "updated"


def test_mixed_keys_keep_defaults_and_do_not_drop_columns():
    from sqlalchemy import text
    url = "sqlite:///" + str(__import__("tempfile").mktemp(suffix=".db"))
    e = create_engine(url)
    with e.begin() as c:
        c.execute(text("create table d (id integer primary key autoincrement, v text default 'd')"))
    ds = SimpleNamespace(kind="sqlite", dsn_encrypted=encrypt_secret(url),
                         id=1, project_id=1)
    SQLSink(ds, {"sink_table": "d", "pk": ["id"],
                 "mode": "upsert"}).write([{"id": 1}, {"id": 2, "v": "x"}, {}])
    with e.connect() as c:
        rows = [tuple(r) for r in c.execute(text("select id, v from d order by id"))]
    assert rows == [(1, "d"), (2, "x"), (3, "d")]
