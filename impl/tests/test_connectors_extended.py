from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf import clickhouse
from odf.connectors.factory import sink_for, source_for
from odf.db import Base
from odf.models import Datasource, Project
from odf.services.datasource import connect_args_for, normalize_dsn
from odf.services.metadata import list_tables, sync_datasource
from odf.workbench.service import run_query


def test_normalize_new_drivers():
    assert normalize_dsn("oracle", "oracle://u:p@h:1521/db") == \
        "oracle+oracledb://u:p@h:1521/db"
    assert normalize_dsn("oracle", "oracle+cx_oracle://u:p@h/db") == \
        "oracle+oracledb://u:p@h/db"
    assert normalize_dsn("mssql", "mssql://u:p@h:1433/db") == \
        "mssql+pymssql://u:p@h:1433/db"
    assert normalize_dsn("sqlserver", "sqlserver://u:p@h/db") == \
        "mssql+pymssql://u:p@h/db"
    assert normalize_dsn("clickhouse", "clickhouse://u:p@h:8123/db") == \
        "clickhouse://u:p@h:8123/db"


def test_connect_args_per_dialect():
    assert connect_args_for("sqlite", "sqlite://") == {}
    assert connect_args_for("oracle", "oracle+oracledb://x") == \
        {"tcp_connect_timeout": 5}
    assert connect_args_for("mssql", "mssql+pymssql://x") == \
        {"login_timeout": 5}
    assert connect_args_for("postgres", "postgresql://x") == \
        {"connect_timeout": 5}


def test_parse_clickhouse_dsn():
    out = clickhouse.parse_dsn(
        "clickhouse://alice:p%40ss@ch.example:8443/analytics?secure=1")
    assert out == {"host": "ch.example", "port": 8443, "username": "alice",
                   "password": "p@ss", "database": "analytics", "secure": True}
    assert clickhouse.parse_dsn("clickhouse://h/db")["port"] == 8123
    assert clickhouse.parse_dsn("clickhouse://h:8443/db")["secure"] is True
    assert clickhouse.parse_dsn("clickhouse+https://h/db")["secure"] is True
    with pytest.raises(ValueError):
        clickhouse.parse_dsn("clickhouse://h:9000/db")


def test_render_inlines_typed_literals():
    sql = clickhouse.render(
        "select * from t where name = :name and n = :n and x is :none",
        {"name": "O'Brien", "n": 5, "none": None})
    assert sql == ("select * from t where name = 'O\\'Brien' and n = 5 "
                   "and x is NULL")
    with pytest.raises(ValueError):
        clickhouse.render("select :missing", {})


class _Result:
    def __init__(self, names, rows):
        self.column_names = names
        self.result_rows = rows


class _FakeClient:
    def __init__(self):
        self.queries = []
        self.closed = False

    def query(self, sql, settings=None, parameters=None):
        self.queries.append(sql)
        if sql.startswith("SHOW TABLES"):
            return _Result(["name"], [("sales",), ("events",)])
        if sql.startswith("DESCRIBE TABLE"):
            return _Result(["name", "type"],
                           [("id", "UInt64"), ("amount", "Float64")])
        return _Result(["id", "name"], [(1, "a"), (2, "b"), (3, "c")])

    def close(self):
        self.closed = True


def test_execute_wraps_limit_and_maps_rows(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(clickhouse, "client_for", lambda ds: fake)
    out = clickhouse.execute(SimpleNamespace(), "select id, name from t",
                             {"min": 1}, 2)
    assert out["columns"] == ["id", "name"]
    assert out["rows"] == [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}]
    assert "LIMIT 2" in fake.queries[0]
    assert fake.closed is True


def test_tables_and_columns(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(clickhouse, "client_for", lambda ds: fake)
    monkeypatch.setattr(clickhouse, "get_dsn",
                        lambda ds: "clickhouse://h:8123/db")
    tables = clickhouse.tables(SimpleNamespace())
    assert [t["table"] for t in tables] == ["sales", "events"]
    cols = clickhouse.columns(SimpleNamespace(), "sales")
    assert cols[0] == {"name": "id", "type": "UInt64"}
    with pytest.raises(ValueError):
        clickhouse.columns(SimpleNamespace(), "sales; drop table x")


def test_factory_supports_oracle_mssql_clickhouse():
    for kind in ("oracle", "mssql", "clickhouse"):
        ds = SimpleNamespace(kind=kind)
        assert source_for(ds, {}) is not None
    for kind in ("clickhouse", "file", "oracle", "mssql"):
        with pytest.raises(ValueError):
            sink_for(SimpleNamespace(kind=kind), {})
    assert sink_for(SimpleNamespace(kind="postgres"), {}) is not None


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="c1", name="c1", status=1))
    s.add(Datasource(id=7, project_id=1, name="ch", kind="clickhouse",
                     dsn_encrypted="x"))
    s.commit()
    return s


def test_clickhouse_metadata_sync(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(clickhouse, "client_for", lambda ds: fake)
    monkeypatch.setattr(clickhouse, "get_dsn",
                        lambda ds: "clickhouse://h:8123/db")
    s = _session()
    assert sync_datasource(s, 7) == 2
    tables = list_tables(s, 7)
    assert [t["table"] for t in tables] == ["sales", "events"]
    assert tables[0]["schema"] == "db"
    assert [c["name"] for c in tables[0]["columns"]] == ["id", "amount"]


def test_clickhouse_workbench_path(monkeypatch):
    s = _session()
    calls = []

    def execute(ds, sql, params, max_rows):
        calls.append((sql, params, max_rows))
        return {"columns": ["n"], "rows": [{"n": 3}]}

    monkeypatch.setattr(clickhouse, "execute", execute)
    out = run_query(s, 1, 7, "select count(*) as n from sales", actor="u")
    assert out["rows"] == [{"n": 3}]
    assert out["truncated"] is False
    assert calls and calls[0][2] == 1001


def test_clickhouse_test_connection_pings(monkeypatch):
    from odf.services.datasource import test_connection
    seen = []

    class Client:
        def command(self, sql):
            seen.append(sql)
            return 1

        def close(self):
            seen.append("closed")

    monkeypatch.setattr(clickhouse, "client_from_dsn", lambda dsn: Client())
    assert test_connection("clickhouse://h/db", kind="clickhouse") is True
    assert seen == ["SELECT 1", "closed"]
