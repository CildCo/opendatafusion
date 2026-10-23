import pyarrow as pa
from sqlalchemy import create_engine, text

from odf.connectors.sql import SQLSink
from odf.pipeline.nodes.base import RunContext
from odf.pipeline.nodes.sink import SinkExecutor


def test_preview_does_not_write(monkeypatch):
    called = {"n": 0}

    class FakeSink:
        def write(self, rows):
            called["n"] += 1
            return len(rows)

    monkeypatch.setattr("odf.pipeline.nodes.sink.sink_for",
                        lambda ds, dag: FakeSink())
    t = pa.Table.from_pylist([{"id": 1}])
    ctx = RunContext(session=None, preview=True)
    out = SinkExecutor().run([t], {"datasource_id": 1, "table": "t"}, ctx)
    assert out.num_rows == 1
    assert called["n"] == 0


def test_sink_passes_mode_and_composite_pk(monkeypatch):
    seen = {}

    class FakeSink:
        def write(self, rows):
            seen["rows"] = rows
            return len(rows)

    class FakeSession:
        def get(self, model, ident):
            return object()

    monkeypatch.setattr("odf.pipeline.nodes.sink.sink_for",
                        lambda ds, dag: seen.update(dag) or FakeSink())
    t = pa.Table.from_pylist([{"a": 1, "b": 2}])
    ctx = RunContext(session=FakeSession(), preview=False)
    SinkExecutor().run(
        [t], {"datasource_id": 1, "table": "t", "pk": ["a", "b"],
              "mode": "append"}, ctx)
    assert seen["pk"] == ["a", "b"]
    assert seen["mode"] == "append"


def _sink_table(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "sink.db"))
    with engine.begin() as c:
        c.execute(text(
            "create table t (a int not null, b int not null, v text, "
            "primary key (a, b))"))
    return engine


def test_sqlsink_append_and_composite_upsert(tmp_path, monkeypatch):
    engine = _sink_table(tmp_path)
    monkeypatch.setattr("odf.connectors.sql.engine_for",
                        lambda ds: engine)

    SQLSink(None, {"sink_table": "t", "pk": ["a", "b"],
                   "mode": "append"}).write(
        [{"a": 1, "b": 1, "v": "a"}, {"a": 1, "b": 2, "v": "b"}])
    with engine.connect() as c:
        assert c.execute(text("select count(*) from t")).scalar() == 2

    SQLSink(None, {"sink_table": "t", "pk": ["a", "b"],
                   "mode": "upsert"}).write([{"a": 1, "b": 1, "v": "x"}])
    with engine.connect() as c:
        assert c.execute(
            text("select v from t where a=1 and b=1")).scalar() == "x"
        assert c.execute(text("select count(*) from t")).scalar() == 2
