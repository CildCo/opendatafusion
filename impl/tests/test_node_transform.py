import duckdb
import pyarrow as pa
import pytest

from odf.pipeline.nodes.base import RunContext
from odf.pipeline.nodes.transform import (CastExecutor, FilterExecutor,
                                          RenameExecutor, SelectExecutor)

T = pa.Table.from_pylist([{"id": 1, "v": "a"}, {"id": 2, "v": "b"}])
CTX = RunContext(session=None)


def test_filter():
    t = FilterExecutor().run(
        [T], {"conditions": [{"column": "id", "op": ">", "value": 1}]}, CTX)
    assert t.num_rows == 1
    assert t.to_pylist()[0]["id"] == 2


def test_select():
    t = SelectExecutor().run(
        [T], {"columns": [{"column": "id", "as": "x"}]}, CTX)
    assert t.column_names == ["x"]


def test_rename():
    t = RenameExecutor().run([T], {"mapping": {"v": "name"}}, CTX)
    assert "name" in t.column_names


def test_cast():
    t = CastExecutor().run([T], {"mapping": {"id": "text"}}, CTX)
    assert t.schema.field("id").type == pa.string()


def test_select_rejects_identifier_injection():
    payload = 'id" FROM read_csv_auto(\'C:/secret.csv\') AS leak --'
    with pytest.raises(ValueError):
        SelectExecutor().run(
            [T], {"columns": [{"column": payload, "as": "x"}]}, CTX)


def test_select_rejects_alias_injection():
    with pytest.raises(ValueError):
        SelectExecutor().run(
            [T], {"columns": [{"column": "id", "as": 'x" --'}]}, CTX)


def test_filter_and_cast_reject_unknown_columns():
    with pytest.raises(ValueError):
        FilterExecutor().run(
            [T], {"conditions": [{"column": "nope", "op": "=", "value": 1}]},
            CTX)
    with pytest.raises(ValueError):
        CastExecutor().run([T], {"mapping": {"nope": "text"}}, CTX)


def test_rename_rejects_alias_injection():
    with pytest.raises(ValueError):
        RenameExecutor().run([T], {"mapping": {"v": 'x" --'}}, CTX)


def test_duckdb_external_access_disabled():
    from odf.pipeline.nodes.transform import _duck
    con = _duck(T)
    try:
        with pytest.raises(duckdb.Error):
            con.execute("SELECT * FROM read_csv_auto('C:/secret.csv')")
    finally:
        con.close()


def test_duckdb_query_timeout_interrupts():
    from odf.pipeline.nodes.transform import _query
    with pytest.raises(Exception):
        _query(T, "SELECT sum(sin(i)) FROM range(1000000000)", timeout=0.05)
