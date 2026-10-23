import pyarrow as pa
import pytest

from odf.pipeline.nodes.base import RunContext
from odf.pipeline.nodes.transform import JoinExecutor

L = pa.Table.from_pylist([{"id": 1, "v": "a"}, {"id": 2, "v": "b"}])
R = pa.Table.from_pylist([{"id": 1, "w": "x"}, {"id": 3, "w": "z"}])


def test_inner_join_keys_and_columns():
    t = JoinExecutor().run(
        [L, R], {"how": "inner", "on": [{"left": "id", "right": "id"}]},
        RunContext(session=None))
    assert t.num_rows == 1
    assert set(t.column_names) == {"id", "v", "w"}


def test_left_join_keeps_left_rows():
    t = JoinExecutor().run(
        [L, R], {"how": "left", "on": [{"left": "id", "right": "id"}]},
        RunContext(session=None))
    assert t.num_rows == 2


def test_join_rejects_missing_key():
    with pytest.raises(ValueError):
        JoinExecutor().run(
            [L, R], {"how": "inner",
                     "on": [{"left": "nope", "right": "id"}]},
            RunContext(session=None))
