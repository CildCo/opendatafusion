from sqlalchemy import create_engine, text

from odf.assets.service import create_asset
from odf.db import SessionLocal
from odf.mcp.server import TOOLS
from odf.models import Datasource
from odf.services.crypto import encrypt_secret


def test_preview_node_returns_rows(tmp_path):
    url = "sqlite:///" + str(tmp_path / "p.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, v text)"))
        c.execute(text("insert into t values (1,'a'),(2,'b')"))
    with SessionLocal() as s:
        ds = Datasource(project_id=1, name="mcp-prev", kind="sqlite",
                        dsn_encrypted=encrypt_secret(url))
        s.add(ds)
        s.commit()
        dsid = ds.id
        content = {"nodes": [
            {"id": "s", "type": "source",
             "config": {"datasource_id": dsid, "table": "t", "pk": "id"}},
            {"id": "o", "type": "sink",
             "config": {"datasource_id": dsid, "table": "t",
                        "pk": ["id"]}}],
            "edges": [{"from": "s", "to": "o"}], "settings": {"batch": 10}}
        a = create_asset(s, 1, "pipeline", "mcp-prev-a", content, "mcp")
        aid = a.id
    out = TOOLS["preview_node"](asset_id=aid, node_id="s", limit=10)
    assert out["rows"][0]["id"] == 1


def test_list_runs_returns_jobs():
    rows = TOOLS["list_runs"](limit=5)
    assert isinstance(rows, list)
