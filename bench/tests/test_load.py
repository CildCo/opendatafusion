import io
import csv

import pyarrow as pa

from bench.generate import load


def test_batch_to_csv_has_no_header_and_keeps_chinese():
    batch = pa.table({"id": [1, 2], "name": ["赵伟", "钱芳"]}).to_batches()[0]
    raw = load.batch_to_csv(batch)
    assert raw == '1,"赵伟"\n2,"钱芳"\n'.encode("utf-8")


def test_batch_to_csv_casts_json_extension():
    batch = pa.table({
        "id": [1],
        "properties": pa.array(['{"a":1}']).cast(pa.json_()),
    }).to_batches()[0]
    raw = load.batch_to_csv(batch).decode("utf-8")
    assert next(csv.reader(io.StringIO(raw))) == ["1", '{"a":1}']
