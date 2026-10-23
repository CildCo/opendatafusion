from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Column, Dataset, Datasource
from odf.services.metadata import list_tables, normalize_table


def test_normalize():
    assert normalize_table("public", "t_user") == "public.t_user"


def test_list_tables():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="d", kind="sqlite",
                     dsn_encrypted="x"))
    s.add(Dataset(id=1, datasource_id=1, schema_name="public", table_name="t"))
    s.add(Column(id=1, dataset_id=1, name="id", data_type="INTEGER"))
    s.commit()
    rows = list_tables(s, 1)
    assert rows[0]["table"] == "t"
    assert rows[0]["columns"][0]["name"] == "id"
