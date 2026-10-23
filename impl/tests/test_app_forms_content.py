from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.appstudio.content import empty_app, validate_app
from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import AssetVersion, Datasource
from odf.services.crypto import encrypt_secret

DATASET = {"mode": "visual", "query": {
    "datasource_id": 1, "table": "t",
    "select": [{"column": "id"}, {"column": "city"}, {"column": "amount"}],
    "filters": [], "limit": 100},
    "params": [], "sql": None, "auth": None}


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "f.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id integer primary key, "
                       "city text, amount int)"))
        c.execute(text("insert into t values (1, 'a', 10)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _dataset(s, content=None):
    ds = create_asset(s, 1, "dataset", "D", content or DATASET, "admin",
                      enabled=False)
    publish_asset(s, ds.id, "admin")
    return ds.id


def _app(s, comp, dataset_id):
    content = {"start_page": "p1", "pages": [{
        "id": "p1", "title": "P", "params": [],
        "components": [{"id": "f", "type": "form",
                        "dataset_id": dataset_id, **comp}]}]}
    a = create_asset(s, 1, "app", "A", content, "admin", enabled=False)
    v = s.get(AssetVersion, a.draft_version_id)
    return v.content_json


FIELDS = [{"column": "city", "widget": "input", "required": True},
          {"column": "amount", "widget": "number"}]


def test_valid_insert_and_update_forms(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    insert = _app(s, {"mode": "insert", "fields": FIELDS}, dsid)
    assert validate_app(s, insert, 1) == []
    update = _app(s, {"mode": "update", "key": "id",
                      "fields": [{"column": "id", "widget": "number",
                                  "required": True}] + FIELDS}, dsid)
    assert validate_app(s, update, 1) == []


def test_form_rejects_alias_column_and_bad_widget(tmp_path):
    s = _env(tmp_path)
    aliased = {**DATASET, "query": {**DATASET["query"], "select": [
        {"column": "id"}, {"column": "city", "as": "town"},
        {"column": "amount"}]}}
    dsid = _dataset(s, aliased)
    a = _app(s, {"mode": "insert", "fields": [
        {"column": "town", "widget": "input"},
        {"column": "amount", "widget": "bogus"}]}, dsid)
    errs = validate_app(s, a, 1)
    assert any("town" in e["message"] for e in errs)
    assert any("widget" in e["field"] for e in errs)


def test_form_select_options_and_update_key(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    no_opts = _app(s, {"mode": "insert", "fields": [
        {"column": "city", "widget": "select"}]}, dsid)
    assert any("options" in e["message"]
               for e in validate_app(s, no_opts, 1))
    no_key = _app(s, {"mode": "update", "fields": FIELDS}, dsid)
    assert any("key" in e["field"]
               for e in validate_app(s, no_key, 1))
    bad_key = _app(s, {"mode": "update", "key": "id", "fields": FIELDS}, dsid)
    assert any("key" in e["field"] for e in
               validate_app(s, bad_key, 1))


def test_unhashable_widget_is_reported(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    a = _app(s, {"mode": "insert", "fields": [
        {"column": "city", "widget": []}]}, dsid)
    assert validate_app(s, a, 1)


def test_delete_form_rules(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    ok = _app(s, {"mode": "delete", "key": "id", "fields": [
        {"column": "id", "widget": "number", "required": True}]}, dsid)
    assert validate_app(s, ok, 1) == []
    no_key = _app(s, {"mode": "delete", "fields": [
        {"column": "id", "widget": "number"}]}, dsid)
    assert any("key" in e["field"]
               for e in validate_app(s, no_key, 1))
    extra = _app(s, {"mode": "delete", "key": "id", "fields": [
        {"column": "id", "widget": "number"},
        {"column": "city", "widget": "input"}]}, dsid)
    assert any("one" in e["message"].lower()
               for e in validate_app(s, extra, 1))


def test_allow_roles_rules(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    ok = _app(s, {"mode": "insert", "allow_roles": ["editor", "admin"],
                  "fields": FIELDS}, dsid)
    assert validate_app(s, ok, 1) == []
    bad = _app(s, {"mode": "insert", "allow_roles": ["owner"],
                   "fields": FIELDS}, dsid)
    assert any("role" in e["field"]
               for e in validate_app(s, bad, 1))
    empty = _app(s, {"mode": "insert", "allow_roles": [],
                     "fields": FIELDS}, dsid)
    assert any("role" in e["field"]
               for e in validate_app(s, empty, 1))


def test_select_default_must_be_an_option(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    ok = _app(s, {"mode": "insert", "fields": [
        {"column": "city", "widget": "select", "options": ["a", "b"],
         "default": "a"}]}, dsid)
    assert validate_app(s, ok, 1) == []
    bad = _app(s, {"mode": "insert", "fields": [
        {"column": "city", "widget": "select", "options": ["a"],
         "default": "b"}]}, dsid)
    assert any("default" in e["field"]
               for e in validate_app(s, bad, 1))


def test_unhashable_allow_roles_is_reported(tmp_path):
    s = _env(tmp_path)
    dsid = _dataset(s)
    a = _app(s, {"mode": "insert", "allow_roles": [["editor"]],
                 "fields": FIELDS}, dsid)
    assert validate_app(s, a, 1)
