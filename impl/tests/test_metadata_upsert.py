import uuid

import pytest
from sqlalchemy import create_engine, text

from odf.models import Column, Dataset, Datasource, QualityRule
from odf.services.crypto import encrypt_secret
from odf.services.metadata import sync_datasource


@pytest.fixture()
def session(tmp_path):
    from sqlalchemy import event
    from sqlalchemy.orm import sessionmaker

    from odf.db import Base
    from odf.models import Project

    # A private database with foreign keys on, so the test matches PostgreSQL
    # without changing the shared pool every other test relies on.
    engine = create_engine("sqlite:///%s" % (tmp_path / "fk.db"))

    @event.listens_for(engine, "connect")
    def _foreign_keys(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Project(id=1, code="md", name="md", status=1))
    s.commit()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _datasource(session, path):
    ds = Datasource(project_id=1, name="md-%s" % uuid.uuid4().hex[:6],
                    kind="sqlite",
                    dsn_encrypted=encrypt_secret("sqlite:///%s" % path))
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds


def test_resync_keeps_dataset_ids_and_quality_rules(session, tmp_path):
    path = tmp_path / "m.db"
    engine = create_engine("sqlite:///%s" % path)
    with engine.begin() as c:
        c.execute(text("create table t (id integer, name text)"))
    engine.dispose()

    ds = _datasource(session, path)
    sync_datasource(session, ds.id)
    first = session.query(Dataset).filter_by(datasource_id=ds.id).one()
    dataset_id = first.id
    rule = QualityRule(project_id=1, dataset_id=dataset_id, name="id not null",
                       kind="not_null", column_name="id", config_json={})
    session.add(rule)
    session.commit()

    engine = create_engine("sqlite:///%s" % path)
    with engine.begin() as c:
        c.execute(text("alter table t add column extra text"))
    engine.dispose()

    sync_datasource(session, ds.id)

    again = session.query(Dataset).filter_by(datasource_id=ds.id).one()
    assert again.id == dataset_id
    cols = {c.name for c in
            session.query(Column).filter_by(dataset_id=dataset_id).all()}
    assert cols == {"id", "name", "extra"}
    assert session.get(QualityRule, rule.id) is not None


def test_resync_drops_tables_that_disappeared(session, tmp_path):
    path = tmp_path / "d.db"
    engine = create_engine("sqlite:///%s" % path)
    with engine.begin() as c:
        c.execute(text("create table keep (id integer)"))
        c.execute(text("create table gone (id integer)"))
    engine.dispose()

    ds = _datasource(session, path)
    sync_datasource(session, ds.id)
    assert session.query(Dataset).filter_by(datasource_id=ds.id).count() == 2

    engine = create_engine("sqlite:///%s" % path)
    with engine.begin() as c:
        c.execute(text("drop table gone"))
    engine.dispose()

    sync_datasource(session, ds.id)
    names = {d.table_name for d in
             session.query(Dataset).filter_by(datasource_id=ds.id).all()}
    assert names == {"keep"}
