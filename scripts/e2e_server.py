import base64
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "impl"))
DB = ROOT / "e2e.db"
DATA = ROOT / "e2e_data"
FILES = ROOT / "e2e_files"

os.environ["ODF_DATABASE_URL"] = "sqlite:///" + str(DB)
os.environ["ODF_JWT_SECRET"] = "e2e-secret-e2e-secret-e2e-secret"
os.environ["ODF_FERNET_KEY"] = base64.urlsafe_b64encode(
    os.urandom(32)).decode()
os.environ["ODF_FILE_DIR"] = str(FILES)
os.environ["ODF_FILE_SOURCE_ROOTS"] = str(FILES)


def seed():
    import sqlite3

    from sqlalchemy import create_engine, text

    from odf.assets.service import create_asset, publish_asset
    from odf.services.masking import create_column_policy
    from odf.db import Base, SessionLocal, engine
    from odf.models import Datasource, Project, User
    from odf.services.crypto import encrypt_secret
    from odf.services.metadata import sync_datasource
    from odf.services.users import hash_password

    Base.metadata.create_all(engine)
    DATA.mkdir(exist_ok=True)
    FILES.mkdir(exist_ok=True)
    demo = DATA / "demo.db"
    raw = create_engine("sqlite:///" + str(demo))
    with raw.begin() as c:
        c.execute(text("create table if not exists demo_src "
                       "(id int primary key, v text)"))
        c.execute(text("create table if not exists demo_dst "
                       "(id int primary key, v text)"))
        c.execute(text("insert or replace into demo_src values "
                       "(1,'a'),(2,'b')"))
    csv = FILES / "demo.csv"
    csv.write_text("id,name\n1,alpha\n2,beta\n", encoding="utf-8")

    with SessionLocal() as s:
        s.add(Project(id=1, code="default", name="Default", status=1))
        s.add(User(id=1, username="e2eadmin", password_hash=hash_password(
            "E2ePassw0rd!"), role="admin", active=True))
        s.add(Datasource(id=1, project_id=1, name="demo sqlite",
                         kind="sqlite",
                         dsn_encrypted=encrypt_secret(
                             "sqlite:///" + str(demo))))
        s.add(Datasource(id=2, project_id=1, name="demo file", kind="file",
                         dsn_encrypted=encrypt_secret(str(csv))))
        s.commit()
        sync_datasource(s, 1)
        sync_datasource(s, 2)
        content = {"nodes": [
            {"id": "src", "type": "source",
             "config": {"datasource_id": 1, "table": "demo_src",
                        "pk": "id", "cursor_column": "id"}},
            {"id": "dst", "type": "sink",
             "config": {"datasource_id": 1, "table": "demo_dst",
                        "pk": ["id"], "mode": "upsert"}}],
            "edges": [{"from": "src", "to": "dst"}],
            "settings": {"batch": 100}}
        a = create_asset(s, 1, "pipeline", "demo pipeline", content,
                         "admin", enabled=False)
        publish_asset(s, a.id, "admin")
        dataset = create_asset(s, 1, "dataset", "demo dataset", {
            "mode": "visual",
            "query": {"datasource_id": 1, "table": "demo_src",
                      "select": [{"column": "id"}, {"column": "v"}],
                      "limit": 100},
            "params": [], "sql": None, "auth": None},
            "admin", enabled=False)
        publish_asset(s, dataset.id, "admin")
        create_column_policy(s, 1, dataset.id, "v", "pii", "redact",
                            ["editor"], "admin")


def main():
    if DB.exists():
        DB.unlink()
    if DATA.exists():
        shutil.rmtree(DATA)
    if FILES.exists():
        shutil.rmtree(FILES)
    seed()
    import uvicorn
    uvicorn.run("odf.main:app", host="127.0.0.1", port=18091, log_level="warning")


if __name__ == "__main__":
    main()
