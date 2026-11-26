from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.appstudio.content import empty_app, validate_app
from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "city"}, {"column": "amount"}],
    "filters": [{"column": "city", "op": "=", "param": "city"}],
    "limit": 100},
    "params": [{"name": "city", "type": "string", "required": False}],
    "sql": None, "auth": None}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "a.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (city text, amount int)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _models(s, dataset=None):
    ds = create_asset(s, 1, "dataset", "D", dataset or DATASET, "admin",
                      enabled=False)
    publish_asset(s, ds.id, "admin")
    mc = {"dataset_id": ds.id,
          "measure": {"agg": "sum", "column": "amount", "as": "value"},
          "dimensions": ["city"], "filters": [],
          "format": {"type": "number"}}
    m = create_asset(s, 1, "metric", "M", mc, "admin", enabled=False)
    publish_asset(s, m.id, "admin")
    return ds.id, m.id


def test_empty_app_is_valid(tmp_path):
    s = _env(tmp_path)
    assert validate_app(s, empty_app(), 1) == []


def test_non_object_content_is_rejected(tmp_path):
    s = _env(tmp_path)
    assert validate_app(s, {}, 1)[0]["field"] == "pages"


def test_valid_app(tmp_path):
    s = _env(tmp_path)
    dsid, mid = _models(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "city", "type": "string"}],
        "components": [
            {"id": "t", "type": "text", "text": "hello"},
            {"id": "m", "type": "metric", "metric_id": mid},
            {"id": "d", "type": "table", "dataset_id": dsid,
             "columns": ["city", "amount"], "limit": 50}]}]}
    assert validate_app(s, content, 1) == []


def test_duplicate_ids_and_missing_start(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": "missing", "pages": [
        {"id": "p1", "title": "P", "params": [], "components": [
            {"id": "x", "type": "text", "text": "a"},
            {"id": "x", "type": "text", "text": "b"}]}]}
    errs = validate_app(s, content, 1)
    assert any("start" in e["field"] for e in errs)
    assert any("duplicate" in e["message"] for e in errs)


def test_dataset_required_param_must_be_exposed(tmp_path):
    s = _env(tmp_path)
    required = {**DATASET,
                "params": [{"name": "city", "type": "string",
                            "required": True}]}
    dsid, _ = _models(s, required)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [{"id": "d", "type": "table",
                        "dataset_id": dsid}]}]}
    assert any("params" in e["field"] for e in validate_app(s, content, 1))


def test_unknown_column_and_unpublished_ref(tmp_path):
    s = _env(tmp_path)
    dsid, _ = _models(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [
            {"id": "d", "type": "table", "dataset_id": dsid,
             "columns": ["nope"]},
            {"id": "m", "type": "metric", "metric_id": 999}]}]}
    errs = validate_app(s, content, 1)
    assert any("column not in dataset" in e["message"] for e in errs)
    assert any(e["field"] == "metric_id" for e in errs)


def test_table_can_bind_only_a_metric(tmp_path):
    s = _env(tmp_path)
    _, mid = _models(s)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [{"id": "m", "type": "table", "metric_id": mid}]}]}
    assert validate_app(s, content, 1) == []


def test_malformed_shapes_are_reported_not_raised(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": [], "pages": [{
        "id": "p1", "title": "P", "params": 5,
        "components": [{"id": "x", "type": [], "text": "a"}]}]}
    errs = validate_app(s, content, 1)
    assert errs


def test_invalid_param_default_is_rejected(tmp_path):
    s = _env(tmp_path)
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P",
        "params": [{"name": "n", "type": "number", "default": "abc"}],
        "components": []}]}
    assert validate_app(s, content, 1)


def _page(components, params=None):
    return {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": params or [],
        "components": components}]}


def test_layout_components_are_valid(tmp_path):
    s = _env(tmp_path)
    content = _page([
        {"id": "h", "type": "heading", "text": "Sales {{city}}",
         "layout": {"x": 0, "y": 0, "w": 12, "h": 1}},
        {"id": "r", "type": "divider", "layout": {"x": 0, "y": 1, "w": 12,
                                                  "h": 1}},
        {"id": "i", "type": "image", "url": "https://example.com/a.png",
         "layout": {"x": 0, "y": 2, "w": 4, "h": 2}},
        {"id": "b", "type": "button", "label": "Details",
         "target_page": "p1", "layout": {"x": 4, "y": 2, "w": 2, "h": 1}},
        {"id": "p", "type": "progress", "value": 60,
         "layout": {"x": 6, "y": 2, "w": 6, "h": 1}},
    ], [{"name": "city", "type": "string"}])
    assert validate_app(s, content, 1) == []


def test_layout_out_of_grid_is_rejected(tmp_path):
    s = _env(tmp_path)
    errs = validate_app(s, _page([
        {"id": "h", "type": "heading", "text": "x",
         "layout": {"x": 10, "y": 0, "w": 4, "h": 1}}]), 1)
    assert any("12 columns" in e["message"] for e in errs)


def test_visibility_requires_a_page_param(tmp_path):
    s = _env(tmp_path)
    errs = validate_app(s, _page([
        {"id": "t", "type": "text", "text": "x",
         "visible_when": {"param": "missing", "op": "=", "value": "1"}}]), 1)
    assert any(e["field"] == "component.visible_when" for e in errs)


def test_binding_requires_a_page_param(tmp_path):
    s = _env(tmp_path)
    errs = validate_app(s, _page([
        {"id": "h", "type": "heading", "text": "Hello {{who}}"}]), 1)
    assert any("binding param not found" in e["message"] for e in errs)


def test_button_target_page_must_exist(tmp_path):
    s = _env(tmp_path)
    errs = validate_app(s, _page([
        {"id": "b", "type": "button", "label": "Go",
         "target_page": "missing"}]), 1)
    assert any(e["field"] == "component.target_page" for e in errs)


def test_progress_value_must_be_percentage(tmp_path):
    s = _env(tmp_path)
    errs = validate_app(s, _page([
        {"id": "p", "type": "progress", "value": 140}]), 1)
    assert any(e["field"] == "component.value" for e in errs)


def test_image_requires_an_allowed_url(tmp_path):
    s = _env(tmp_path)
    errs = validate_app(s, _page([
        {"id": "i", "type": "image", "url": "javascript:alert(1)"}]), 1)
    assert any(e["field"] == "component.url" for e in errs)


def test_app_bindings_actions_and_roles(tmp_path):
    s = _env(tmp_path)
    content = _page([
        {"id": "t", "type": "text", "text": "Hello {{params.city}}",
         "layout": {"x": 0, "y": 0, "w": 12, "h": 1}},
        {"id": "h", "type": "heading",
         "text": "{{components.tbl.selectedRow.city}}",
         "layout": {"x": 0, "y": 1, "w": 12, "h": 1}},
        {"id": "tbl", "type": "table", "dataset_id": 1,
         "layout": {"x": 0, "y": 2, "w": 12, "h": 4}},
        {"id": "b", "type": "button", "label": "Go",
         "actions": [
             {"type": "set_param", "param": "city", "value": "beijing"},
             {"type": "message", "text": "done"},
             {"type": "navigate", "page": "p1"},
         ],
         "visible_roles": ["editor", "admin"],
         "layout": {"x": 0, "y": 6, "w": 3, "h": 2}},
    ], [{"name": "city", "type": "string"}])
    # Dataset asset is not created in this fixture, so only structural and
    # non-dataset errors are interesting here.
    errs = validate_app(s, content, 1)
    assert not any(e["field"] == "component.text" for e in errs)
    assert not any(e["field"] == "component.actions.type" for e in errs)

    bad = _page([
        {"id": "t", "type": "text", "text": "{{params.missing}}"},
        {"id": "b", "type": "button", "label": "Go",
         "actions": [{"type": "navigate", "page": "missing"}],
         "visible_roles": ["owner"]},
    ], [{"name": "city", "type": "string"}])
    errs = validate_app(s, bad, 1)
    assert any("binding param" in e["message"] for e in errs)
    assert any("target page" in e["message"] for e in errs)
    assert any(e["field"] == "component.visible_roles" for e in errs)

    bad_action = _page([
        {"id": "b", "type": "button", "label": "Go",
         "actions": [{"type": "set_param", "param": "missing",
                      "value": 1}]},
    ], [{"name": "city", "type": "string"}])
    assert any("param is not declared" in e["message"]
               for e in validate_app(s, bad_action, 1))


def test_container_and_tabs_content_validation(tmp_path):
    s = _env(tmp_path)
    content = {
        "start_page": "p1",
        "pages": [{
            "id": "p1",
            "title": "P",
            "params": [{"name": "city", "type": "string", "default": "a"}],
            "components": [
                {"id": "box", "type": "container", "title": "Box",
                 "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
                 "children": [
                     {"id": "txt", "type": "text",
                      "text": "Hello {{params.city}}",
                      "layout": {"x": 0, "y": 0, "w": 6, "h": 1}}]},
                {"id": "tabs", "type": "tabs",
                 "tabs": [{"id": "t1", "title": "One", "components": [
                     {"id": "go", "type": "button", "label": "Go",
                      "actions": [{"type": "navigate", "page": "p1"}]}]}],
                 "layout": {"x": 6, "y": 0, "w": 6, "h": 4}},
                {"id": "modal", "type": "modal", "label": "More",
                 "title": "More",
                 "children": [{"id": "h2", "type": "heading",
                               "text": "Inside"}]},
            ],
        }],
    }
    errs = validate_app(s, content, 1)
    assert errs == []


def test_container_validation_rejects_bad_nesting(tmp_path):
    s = _env(tmp_path)
    content = {
        "start_page": "p1",
        "pages": [{
            "id": "p1",
            "title": "P",
            "params": [],
            "components": [
                {"id": "box", "type": "container", "children": [
                    {"id": "a", "type": "text", "text": "ok",
                     "visible_roles": ["nobody"]}]},
                {"id": "tabs", "type": "tabs", "tabs": []},
                {"id": "a", "type": "text", "text": "duplicate"},
                {"id": "modal", "type": "modal", "label": 5},
            ],
        }],
    }
    messages = [e["message"] for e in validate_app(s, content, 1)]
    assert any("visible_roles" in m for m in messages)
    assert any("tabs" in m for m in messages)
    assert any("duplicate component id" in m for m in messages)
    assert any("modal" in m or "label" in m for m in messages)


def test_container_depth_is_limited(tmp_path):
    s = _env(tmp_path)
    inner = {"id": "leaf", "type": "text", "text": "deep"}
    for i in range(6):
        inner = {"id": f"box{i}", "type": "container",
                 "children": [inner]}
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [inner]}]}
    messages = [e["message"] for e in validate_app(s, content, 1)]
    assert any("nesting" in m or "depth" in m for m in messages)
