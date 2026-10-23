from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.api.openapi_gateway import resolve_api_asset
from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Datasource, Project
from odf.services.crypto import encrypt_secret


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "gw.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int)"))
        c.execute(text("insert into t values (1)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p1", name="P1", status=1))
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def test_resolve_api_asset(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "t",
                         "select": [{"column": "id"}]},
               "params": [], "sql": None,
               "auth": {"type": "aksk", "rate_limit_per_min": 60}}
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    assert resolve_api_asset(s, "p1", a.key).id == a.id


def test_resolve_returns_none_for_other_project(tmp_path):
    s = _env(tmp_path)
    content = {"mode": "visual",
               "query": {"datasource_id": 1, "table": "t",
                         "select": [{"column": "id"}]},
               "params": [], "sql": None}
    a = create_asset(s, 1, "api", "A", content, "admin", enabled=False)
    assert resolve_api_asset(s, "other", a.key) is None
