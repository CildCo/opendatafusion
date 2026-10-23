import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Datasource
from odf.pipeline.preview import preview_pipeline


@pytest.fixture()
def s():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    with sessionmaker(bind=e)() as sess:
        sess.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                            dsn_encrypted="x"))
        sess.commit()
        yield sess


def test_preview_returns_filtered_rows(s, monkeypatch):
    class FakeSource:
        def read(self, cursor, limit):
            return [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}], '["2","2"]'

    monkeypatch.setattr("odf.pipeline.nodes.source.source_for",
                        lambda ds, dag: FakeSource())

    content = {"nodes": [
        {"id": "src", "type": "source",
         "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
        {"id": "f", "type": "filter",
         "config": {"conditions": [{"column": "id", "op": ">", "value": 1}]}}],
        "edges": [{"from": "src", "to": "f"}],
        "settings": {"batch": 10}}
    a = create_asset(s, 1, "pipeline", "p", content, "admin")
    r = preview_pipeline(s, a.id, "f", limit=100)
    assert len(r["rows"]) == 1
    assert r["node_stats"]["src"]["rows"] == 2
    assert r["node_stats"]["f"]["rows"] == 1


def test_preview_clamps_batch_and_accepts_override(s, monkeypatch):
    seen = {}

    class FakeSource:
        def read(self, cursor, limit):
            seen["limit"] = limit
            return [{"id": 1, "v": "a"}], None

    monkeypatch.setattr("odf.pipeline.nodes.source.source_for",
                        lambda ds, dag: FakeSource())

    draft = {"nodes": [], "edges": []}
    a = create_asset(s, 1, "pipeline", "p", draft, "admin")
    override = {"nodes": [
        {"id": "src", "type": "source",
         "config": {"datasource_id": 1, "table": "t", "pk": "id"}},
        {"id": "f", "type": "filter",
         "config": {"conditions": [{"column": "id", "op": ">", "value": 0}]}}],
        "edges": [{"from": "src", "to": "f"}],
        "settings": {"batch": 1000000}}
    r = preview_pipeline(s, a.id, "f", limit=100, content=override)
    assert r["rows"] == [{"id": 1, "v": "a"}]
    assert seen["limit"] <= 1000


def test_preview_rejects_unknown_node(s):
    a = create_asset(s, 1, "pipeline", "p", {"nodes": [], "edges": []},
                     "admin")
    with pytest.raises(ValueError):
        preview_pipeline(s, a.id, "missing")
