import pytest

from odf.pipeline.nodes.source import SourceExecutor


class _Reader:
    def read(self, cursor, limit):
        return ([{"payload": {"op": "c", "after": {"id": 1, "city": "a"}}},
                 {"payload": {"op": "d", "after": None}},
                 {"id": 3, "city": "raw"}], "cursor")


class _Session:
    def get(self, model, key):
        return object()


class _Ctx:
    def __init__(self):
        self.session = _Session()
        self.current_node = "s"
        self.cursors = {}
        self.cursor_override = {}
        self.batch = 100
        self.until_cursor = None
        self.exhausted_nodes = set()
        self.new_cursors = {}


def test_debezium_payload_is_unwrapped(monkeypatch):
    import odf.pipeline.nodes.source as module
    monkeypatch.setattr(module, "source_for", lambda ds, dag: _Reader())
    ctx = _Ctx()
    table = SourceExecutor().run(
        [], {"datasource_id": 1, "table": "t", "debezium": True}, ctx)
    assert table.to_pylist() == [{"id": 1, "city": "a"}]
    assert ctx.new_cursors["s"] == "cursor"


def test_plain_kafka_messages_stay_unchanged(monkeypatch):
    import odf.pipeline.nodes.source as module
    monkeypatch.setattr(module, "source_for", lambda ds, dag: _Reader())
    ctx = _Ctx()
    table = SourceExecutor().run(
        [], {"datasource_id": 1, "table": "t"}, ctx)
    assert len(table.to_pylist()) == 3
