from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Column, Dataset, Datasource
from odf.services.catalog import (create_tag, dataset_detail, lineage,
                                  list_datasets, tag_dataset)
from odf.services.flow import create_flow


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_catalog_and_lineage():
    s = _session()
    s.add(Datasource(id=1, project_id=1, name="src", kind="sqlite",
                     dsn_encrypted="x"))
    s.add(Datasource(id=2, project_id=1, name="dst", kind="sqlite",
                     dsn_encrypted="x"))
    s.add(Dataset(id=1, datasource_id=1, schema_name="main", table_name="a"))
    s.add(Dataset(id=2, datasource_id=2, schema_name="main", table_name="b"))
    s.add(Column(id=1, dataset_id=1, name="id", data_type="INTEGER"))
    s.commit()
    create_flow(s, 1, "copy", "0 */5 * * * ?", {
        "source_ds_id": 1, "sink_ds_id": 2,
        "source_table": "a", "sink_table": "b", "pk": "id"})
    view = lineage(s, 1)
    assert view["edges"][0]["from"] == "1:a"
    assert view["edges"][0]["to"] == "2:b"
    assert list_datasets(s, 1)
    assert dataset_detail(s, 1)["columns"][0]["name"] == "id"


def test_tag_dataset():
    s = _session()
    s.add(Dataset(id=1, datasource_id=1, schema_name="main", table_name="a"))
    s.commit()
    t = create_tag(s, 1, "core")
    tag_dataset(s, 1, t.id)
    assert dataset_detail(s, 1)["tags"] == ["core"]
