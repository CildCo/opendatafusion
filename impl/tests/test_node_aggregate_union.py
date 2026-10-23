import pyarrow as pa
import pytest

from odf.pipeline.nodes.base import RunContext
from odf.pipeline.nodes.transform import AggregateExecutor, UnionExecutor

T = pa.Table.from_pylist([
    {"city": "a", "amount": 10}, {"city": "a", "amount": 5},
    {"city": "b", "amount": 7}])
CTX = RunContext(session=None)


def test_aggregate_sum():
    t = AggregateExecutor().run(
        [T], {"group_by": ["city"],
              "aggregates": [{"column": "amount", "agg": "sum",
                              "as": "total"}]}, CTX)
    rows = sorted(t.to_pylist(), key=lambda r: r["city"])
    assert rows == [{"city": "a", "total": 15}, {"city": "b", "total": 7}]


def test_union_all_aligns_columns():
    other = pa.Table.from_pylist([{"city": "c", "amount": 1}])
    t = UnionExecutor().run(
        [T, other], {"all": True, "columns": [
            {"name": "city", "left": "city", "right": "city"},
            {"name": "amount", "left": "amount", "right": "amount"}]}, CTX)
    assert t.num_rows == 4


def test_union_missing_column_is_rejected():
    other = pa.Table.from_pylist([{"city": "c"}])
    with pytest.raises(ValueError):
        UnionExecutor().run(
            [T, other], {"all": True, "columns": [
                {"name": "amount", "left": "amount", "right": "amount"}]},
            CTX)


def test_aggregate_alias_collision_is_rejected():
    with pytest.raises(ValueError):
        AggregateExecutor().run(
            [T], {"group_by": ["city"],
                  "aggregates": [{"column": "amount", "agg": "sum",
                                  "as": "city"}]}, CTX)


def test_union_duplicate_output_is_rejected():
    other = pa.Table.from_pylist([{"city": "c", "amount": 1}])
    with pytest.raises(ValueError):
        UnionExecutor().run(
            [T, other], {"columns": [
                {"name": "x", "left": "city", "right": "city"},
                {"name": "x", "left": "amount", "right": "amount"}]}, CTX)
