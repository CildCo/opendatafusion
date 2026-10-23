import pyarrow as pa
import pytest

from odf.pipeline.nodes.base import RunContext
from odf.pipeline.nodes.transform import DedupeExecutor, QualityExecutor

T = pa.Table.from_pylist([
    {"id": 1, "v": "a"}, {"id": 1, "v": "b"}, {"id": 2, "v": "c"}])
CTX = RunContext(session=None)


def test_dedupe_keeps_one_per_key():
    t = DedupeExecutor().run([T], {"keys": ["id"], "keep": "first"}, CTX)
    assert t.num_rows == 2


def test_quality_fail_raises():
    with pytest.raises(ValueError):
        QualityExecutor().run(
            [T], {"rules": [{"column": "id", "op": ">", "value": 1}],
                  "on_fail": "fail"}, CTX)


def test_quality_quarantine_returns_passing_rows():
    t = QualityExecutor().run(
        [T], {"rules": [{"column": "id", "op": ">", "value": 1}],
              "on_fail": "quarantine"}, CTX)
    assert t.num_rows == 1


def test_dedupe_keep_last_without_order():
    t = DedupeExecutor().run([T], {"keys": ["id"], "keep": "last"}, CTX)
    rows = [r for r in t.to_pylist() if r["id"] == 1]
    assert rows == [{"id": 1, "v": "b"}]
