import pytest
from sqlalchemy import create_engine, text

from odf.connectors.factory import source_for
from odf.connectors.trino import TrinoSource
from odf.models import Datasource
from odf.services.datasource import (create_datasource, get_dsn,
                                     test_connection as check_connection)
from odf.services.query import execute_query


class _FakeClient:
    def __init__(self, result=None):
        self.statements = []
        self._result = result or {"columns": ["id"], "rows": [{"id": 1}],
                                  "row_count": 1, "truncated": False}

    def query(self, sql, max_rows=1000):
        self.statements.append((sql, max_rows))
        return self._result


@pytest.fixture()
def session():
    from odf.db import SessionLocal
    with SessionLocal() as s:
        yield s


def _trino_ds(session, name="lake"):
    return create_datasource(
        session, 1, name, "trino://odf@trino:8080/iceberg/demo", "trino")


def test_create_datasource_keeps_trino_dsn(session):
    ds = _trino_ds(session, "lake-keep")
    assert ds.kind == "trino"
    assert get_dsn(ds) == "trino://odf@trino:8080/iceberg/demo"


def test_test_connection_uses_trino_ping(monkeypatch):
    calls = []

    def fake_ping(self):
        calls.append(self.base_url)
        return True

    monkeypatch.setattr("odf.trino.client.TrinoClient.ping", fake_ping)
    assert check_connection("trino://odf@lake:8080/iceberg/demo",
                            kind="trino") is True
    assert calls == ["http://lake:8080"]


def test_factory_returns_trino_source():
    ds = Datasource(id=11, project_id=1, name="lake", kind="trino",
                    dsn_encrypted="x")
    src = source_for(ds, {"source_table": "demo.events", "pk": "id"})
    assert isinstance(src, TrinoSource)


def test_trino_source_reads_with_composite_cursor(monkeypatch):
    fake = _FakeClient({"columns": ["id", "seq", "name"],
                        "rows": [{"id": 2, "seq": 20, "name": "b"},
                                 {"id": 3, "seq": 30, "name": "c"}],
                        "row_count": 2, "truncated": False})
    monkeypatch.setattr("odf.connectors.trino.client_for_datasource",
                        lambda ds: fake)
    ds = Datasource(id=12, project_id=1, name="lake", kind="trino",
                    dsn_encrypted="x")
    src = TrinoSource(ds, {"source_table": "demo.events", "pk": "seq",
                           "cursor_column": "id"})
    rows, cursor = src.read('["1", "9"]', 100)

    sql, limit = fake.statements[0]
    assert 'FROM "demo"."events"' in sql
    assert '(("id" > 1) OR ("id" = 1 AND "seq" > 9))' in sql
    assert 'ORDER BY "id", "seq"' in sql
    assert limit == 100
    assert [r["id"] for r in rows] == [2, 3]
    assert cursor == '["3", "30"]'


def test_trino_source_rejects_bad_identifier():
    ds = Datasource(id=13, project_id=1, name="lake", kind="trino",
                    dsn_encrypted="x")
    src = TrinoSource(ds, {"source_table": "demo.events; drop table x",
                           "pk": "id"})
    with pytest.raises(ValueError, match="invalid identifier"):
        src.read(None, 10)


def test_execute_query_routes_trino(monkeypatch):
    fake = _FakeClient({"columns": ["n"], "rows": [{"n": 1}],
                        "row_count": 1, "truncated": False})
    monkeypatch.setattr("odf.services.query.client_for_datasource",
                        lambda ds: fake)
    ds = Datasource(id=14, project_id=1, name="lake", kind="trino",
                    dsn_encrypted="x")
    out = execute_query(None, ds, "select :v as n", {"v": "a'b"}, 10)
    assert out["rows"] == [{"n": 1}]
    assert fake.statements[0][0] == "select 'a''b' as n"


def test_execute_query_runs_sql_sources(tmp_path):
    db = tmp_path / "src.db"
    engine = create_engine("sqlite:///%s" % db)
    with engine.begin() as c:
        c.execute(text("create table t (id integer, name text)"))
        c.execute(text("insert into t values (1, 'a'), (2, 'b')"))
    engine.dispose()

    from odf.services.crypto import encrypt_secret
    ds = Datasource(id=15, project_id=1, name="local", kind="sqlite",
                    dsn_encrypted=encrypt_secret("sqlite:///%s" % db))
    out = execute_query(None, ds, "select * from t order by id", None, 1)
    assert out["columns"] == ["id", "name"]
    assert out["rows"] == [{"id": 1, "name": "a"}]
    assert out["row_count"] == 1


def test_execute_query_reports_failure(tmp_path):
    from odf.services.crypto import encrypt_secret
    ds = Datasource(id=16, project_id=1, name="local", kind="sqlite",
                    dsn_encrypted=encrypt_secret(
                        "sqlite:///%s" % (tmp_path / "empty.db")))
    with pytest.raises(ValueError, match="query failed"):
        execute_query(None, ds, "select * from missing", None, 10)
