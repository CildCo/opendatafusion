import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.apistudio.catalog import table_columns
from odf.db import Base
from odf.models import Column, Dataset, Datasource
from odf.services.crypto import encrypt_secret


def _session(tmp_path):
    url = "sqlite:///" + str(tmp_path / "cat.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, name text)"))
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def test_live_introspection(tmp_path):
    s = _session(tmp_path)
    ds = s.get(Datasource, 1)
    assert table_columns(s, ds, "t") == ["id", "name"]


def test_synced_metadata_is_preferred(tmp_path):
    s = _session(tmp_path)
    ds = s.get(Datasource, 1)
    d = Dataset(datasource_id=1, schema_name="main", table_name="t")
    s.add(d)
    s.flush()
    s.add_all([Column(dataset_id=d.id, name="a", data_type="int"),
               Column(dataset_id=d.id, name="b", data_type="text")])
    s.commit()
    assert table_columns(s, ds, "main.t") == ["a", "b"]


def test_unknown_table_raises(tmp_path):
    s = _session(tmp_path)
    ds = s.get(Datasource, 1)
    with pytest.raises(ValueError):
        table_columns(s, ds, "missing")
