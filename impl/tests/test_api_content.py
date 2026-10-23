from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.apistudio.content import empty_content, validate_content
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret


def _s(tmp_path):
    url = "sqlite:///" + str(tmp_path / "c.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, city text, amount int)"))
        c.execute(text('create table q ("delete" text)'))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def test_empty_content_is_invalid(tmp_path):
    s = _s(tmp_path)
    assert validate_content(s, empty_content(), 1)


def test_valid_visual_content(tmp_path):
    s = _s(tmp_path)
    content = {
        "mode": "visual",
        "query": {"datasource_id": 1, "table": "t",
                  "select": [{"column": "city"}],
                  "filters": [{"column": "id", "op": ">", "param": "min"}],
                  "limit": 100},
        "sql": None,
        "params": [{"name": "min", "type": "number", "required": True}],
        "auth": {"type": "aksk", "rate_limit_per_min": 60},
    }
    assert validate_content(s, content, 1) == []


def test_visual_unknown_table_and_column(tmp_path):
    s = _s(tmp_path)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "t",
                         "select": [{"column": "nope"}]},
               "params": []}
    errs = validate_content(s, content, 1)
    assert any("nope" in e["message"] for e in errs)


def test_sql_undeclared_placeholder_and_mutation(tmp_path):
    s = _s(tmp_path)
    base = {"mode": "sql", "query": {"datasource_id": 1}, "params": []}
    assert validate_content(s, {**base, "sql": "select ${x}"}, 1)
    assert validate_content(s, {**base, "sql": "delete from t"}, 1)


def test_cross_project_datasource_is_rejected(tmp_path):
    s = _s(tmp_path)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "t",
                         "select": [{"column": "city"}]},
               "params": []}
    assert validate_content(s, content, 2)


def test_quoted_forbidden_word_column_is_valid(tmp_path):
    s = _s(tmp_path)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "q",
                         "select": [{"column": "delete"}]},
               "params": []}
    assert validate_content(s, content, 1) == []
