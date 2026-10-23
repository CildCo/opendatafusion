import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.apistudio.service import (ApiError, build_docs, execute_published,
                                   preview_api)
from odf.assets.service import create_asset, update_draft
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret


@pytest.fixture()
def env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "svc.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, city text, amount int)"))
        c.execute(text("insert into t values (1,'a',10),(2,'b',20)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    content = {
        "mode": "visual",
        "query": {"datasource_id": 1, "table": "t",
                  "select": [{"column": "id"}, {"column": "city"}],
                  "filters": [{"column": "id", "op": ">", "param": "min"}],
                  "limit": 100},
        "sql": None,
        "params": [{"name": "min", "type": "number", "required": True}],
        "auth": {"type": "aksk", "rate_limit_per_min": 60},
    }
    return s, content


def test_preview_visual(env):
    s, content = env
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    r = preview_api(s, a.id, {"min": 1})
    assert r["row_count"] == 1
    assert r["rows"][0]["city"] == "b"
    assert "SELECT" in r["sql"]


def test_preview_accepts_unsaved_content(env):
    s, content = env
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    override = {**content, "query": {**content["query"], "select": [
        {"column": "city"}]}}
    r = preview_api(s, a.id, {"min": 0}, content=override)
    assert r["rows"] == [{"city": "a"}, {"city": "b"}]


def test_missing_parameter_is_structured(env):
    s, content = env
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    with pytest.raises(ApiError) as e:
        preview_api(s, a.id, {})
    assert e.value.parameter == "min"


def test_sql_mode_runs_and_rejects_dml(env):
    s, content = env
    sql_content = {**content, "mode": "sql",
                   "sql": "select city from t where id > ${min}"}
    a = create_asset(s, 1, "api", "A", sql_content, "admin", enabled=False)
    assert preview_api(s, a.id, {"min": 0})["row_count"] == 2
    bad = {**sql_content, "sql": "delete from t"}
    b = create_asset(s, 1, "api", "B", bad, "admin", enabled=False)
    with pytest.raises(ApiError):
        preview_api(s, b.id, {"min": 0})


def test_execute_published_requires_published_version(env):
    s, content = env
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    with pytest.raises(ApiError):
        execute_published(s, a.id, {"min": 0})


def test_execute_published_ignores_newer_draft(env):
    s, content = env
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    a.enabled = True
    a.published_version_id = a.draft_version_id
    s.commit()
    update_draft(s, a.id, {**content, "query": {
        **content["query"], "select": [{"column": "city"}]}}, "admin")
    r = execute_published(s, a.id, {"min": 0})
    assert r["columns"] == ["id", "city"]
    assert r["row_count"] == 2


def test_docs_contains_endpoint_and_examples(env):
    s, content = env
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    docs = build_docs(a, content)
    assert docs["path"] == "/openapi/%s" % a.key
    assert "curl" in docs and "python" in docs
    assert docs["params"][0]["name"] == "min"


def test_empty_in_list_is_an_api_error(env):
    s, content = env
    c = {**content, "query": {**content["query"], "filters": [
        {"column": "id", "op": "in", "param": "ids"}]},
         "params": [{"name": "ids", "type": "number", "required": True}]}
    a = create_asset(s, 1, "api", "A", c, "admin", enabled=False)
    with pytest.raises(ApiError):
        preview_api(s, a.id, {"ids": []})


def test_unknown_sql_table_is_an_api_error(env):
    s, content = env
    c = {**content, "mode": "sql",
         "sql": "select * from missing_table"}
    a = create_asset(s, 1, "api", "A", c, "admin", enabled=False)
    with pytest.raises(ApiError):
        preview_api(s, a.id, {"min": 0})


def test_raw_bind_is_an_api_error(env):
    s, content = env
    c = {**content, "mode": "sql", "sql": "select * from t where id = :x"}
    a = create_asset(s, 1, "api", "A", c, "admin", enabled=False)
    with pytest.raises(ApiError):
        preview_api(s, a.id, {"min": 0})


def test_negative_limit_is_clamped(env, monkeypatch):
    s, content = env

    class FakeSettings:
        query_max_rows = 1
        query_timeout_s = 60

    monkeypatch.setattr("odf.apistudio.service.get_settings",
                        lambda: FakeSettings())
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    assert preview_api(s, a.id, {"min": 0}, limit=-1)["row_count"] == 1
