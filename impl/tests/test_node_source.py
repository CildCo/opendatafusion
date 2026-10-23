import pyarrow as pa
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Datasource
from odf.pipeline.nodes.base import RunContext
from odf.pipeline.nodes.source import SourceExecutor


def test_source_reads_rows(monkeypatch):
    class FakeSource:
        def read(self, cursor, limit):
            return [{"id": 1, "v": "a"}], '["1","1"]'

    monkeypatch.setattr(
        "odf.pipeline.nodes.source.source_for",
        lambda ds, dag: FakeSource())

    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as s:
        s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                         dsn_encrypted="x"))
        s.commit()
        ctx = RunContext(session=s, batch=10, current_node="src")
        t = SourceExecutor().run([], {"datasource_id": 1, "table": "t",
                                      "pk": "id"}, ctx)
        assert isinstance(t, pa.Table)
        assert t.num_rows == 1
        assert ctx.new_cursors["src"] == '["1","1"]'


def test_source_empty_preserves_columns(tmp_path):
    from sqlalchemy import text
    from odf.services.crypto import encrypt_secret

    class FakeSource:
        def read(self, cursor, limit):
            return [], None

    monkeypatch = __import__("pytest").MonkeyPatch()
    monkeypatch.setattr("odf.pipeline.nodes.source.source_for",
                        lambda ds, dag: FakeSource())
    url = "sqlite:///" + str(tmp_path / "s.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, v text)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as s:
        s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                         dsn_encrypted=encrypt_secret(url)))
        s.commit()
        ctx = RunContext(session=s, batch=10, current_node="src")
        t = SourceExecutor().run([], {"datasource_id": 1, "table": "t",
                                      "pk": "id"}, ctx)
        assert t.column_names == ["id", "v"]
        assert t.num_rows == 0
    monkeypatch.undo()
