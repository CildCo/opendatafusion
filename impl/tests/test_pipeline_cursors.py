import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import AssetVersion, Project
from odf.pipeline.cursors import list_cursors, set_cursor


def _asset():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="c1", name="c1", status=1))
    content = {"nodes": [
        {"id": "s", "type": "source",
         "config": {"datasource_id": 1, "table": "events", "pk": "id",
                    "cursor_column": "id"}},
        {"id": "s2", "type": "source",
         "config": {"datasource_id": 2, "table": "other", "pk": "id"}},
        {"id": "k", "type": "sink",
         "config": {"datasource_id": 3, "table": "dest", "pk": ["id"]}},
    ], "edges": [{"from": "s", "to": "k"}, {"from": "s2", "to": "k"}],
        "settings": {}}
    a = create_asset(s, 1, "pipeline", "P", content, "admin", enabled=False)
    a.cursor_json = {"s": "[1,1]", "stale": "x"}
    s.commit()
    return s, a


def test_list_cursors_exposes_sources_only():
    s, a = _asset()
    out = list_cursors(s, a)
    assert out["cursors"] == {"s": "[1,1]", "stale": "x"}
    assert [x["node_id"] for x in out["sources"]] == ["s", "s2"]
    assert out["sources"][0]["cursor"] == "[1,1]"
    assert out["sources"][1]["cursor"] is None


def test_list_cursors_prefers_published_version():
    s, a = _asset()
    v = AssetVersion(asset_id=a.id, version=2, status="published",
                     created_by="admin", content_json={"nodes": [
                         {"id": "pub", "type": "source",
                          "config": {"datasource_id": 1, "table": "events",
                                     "pk": "id", "cursor_column": "id"}}]})
    s.add(v)
    s.flush()
    a.published_version_id = v.id
    s.commit()
    out = list_cursors(s, a)
    assert [x["node_id"] for x in out["sources"]] == ["pub"]


def test_set_cursor_updates_and_clears():
    s, a = _asset()
    out = set_cursor(s, a, "s", "42")
    assert out["cursors"]["s"] == "42"
    assert a.cursor_json["s"] == "42"
    set_cursor(s, a, "s2", "2026-01-01")
    assert a.cursor_json["s2"] == "2026-01-01"
    set_cursor(s, a, "s", None)
    assert "s" not in a.cursor_json
    assert a.cursor_json["s2"] == "2026-01-01"


def test_set_cursor_rejects_non_source_and_bad_values():
    s, a = _asset()
    with pytest.raises(ValueError):
        set_cursor(s, a, "k", "1")
    with pytest.raises(ValueError):
        set_cursor(s, a, "missing", "1")
    with pytest.raises(ValueError):
        set_cursor(s, a, "s", "   ")
    with pytest.raises(ValueError):
        set_cursor(s, a, "s", {"x": 1})
