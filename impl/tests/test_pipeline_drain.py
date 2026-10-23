import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.crypto import encrypt_secret
from odf.services.jobs import enqueue_asset, process_job


def test_one_job_drains_all_batches(tmp_path):
    db = tmp_path / "drain.db"
    con = sqlite3.connect(db)
    con.execute("create table src (id int primary key, v text)")
    con.execute("create table dst (id int primary key, v text)")
    con.executemany("insert into src values (?, ?)",
                    [(i, "v%d" % i) for i in range(1, 6)])
    con.commit()
    con.close()

    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret("sqlite:///" + str(db))))
    s.commit()
    content = {"nodes": [
        {"id": "src", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id",
                    "cursor_column": "id"}},
        {"id": "dst", "type": "sink",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"],
                    "mode": "upsert"}}],
        "edges": [{"from": "src", "to": "dst"}], "settings": {"batch": 2}}
    asset = create_asset(s, 1, "pipeline", "drain", content, "admin")
    publish_asset(s, asset.id, "admin")
    job = enqueue_asset(s, asset.id)
    process_job(s, job, "w1")
    s.refresh(job)
    assert job.status == "success"
    con = sqlite3.connect(db)
    assert con.execute("select count(*) from dst").fetchone()[0] == 5
    con.close()
