from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.pipeline.preview import preview_pipeline
from odf.services.crypto import encrypt_secret
from odf.services.jobs import enqueue_asset, process_job


def test_pipeline_end_to_end(tmp_path):
    db = tmp_path / "e2e.db"
    url = "sqlite:///" + str(db)
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table src (id int primary key, v text)"))
        c.execute(text("create table dst (id int primary key, v text)"))
        for i in range(1, 6):
            c.execute(text("insert into src values (:i, :v)"),
                      {"i": i, "v": "v%d" % i})

    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()

    content = {"nodes": [
        {"id": "src", "type": "source",
         "config": {"datasource_id": 1, "table": "src", "pk": "id"}},
        {"id": "f", "type": "filter",
         "config": {"conditions": [{"column": "id", "op": ">", "value": 2}]}},
        {"id": "dst", "type": "sink",
         "config": {"datasource_id": 1, "table": "dst", "pk": ["id"],
                    "mode": "upsert"}}],
        "edges": [{"from": "src", "to": "f"}, {"from": "f", "to": "dst"}],
        "settings": {"batch": 100}}
    a = create_asset(s, 1, "pipeline", "e2e", content, "admin")
    preview = preview_pipeline(s, a.id, "f", limit=100)
    assert len(preview["rows"]) == 3

    publish_asset(s, a.id, "admin")
    job = enqueue_asset(s, a.id)
    process_job(s, job, "w1")
    s.refresh(job)
    assert job.status == "success"

    raw2 = create_engine(url)
    with raw2.connect() as c:
        n = c.execute(text("select count(*) from dst")).scalar()
    assert n == 3
