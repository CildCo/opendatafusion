from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Column, Dataset
from odf.services.standards import (compliance, create_standard,
                                    list_mappings, map_standard)


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_standard_mapping_and_compliance():
    s = _session()
    s.add(Dataset(id=1, datasource_id=1, schema_name="main", table_name="t"))
    s.add(Column(id=1, dataset_id=1, name="id", data_type="INTEGER"))
    s.add(Column(id=2, dataset_id=1, name="name", data_type="TEXT"))
    s.commit()
    std = create_standard(s, 1, "STD-001", "ID standard")
    map_standard(s, std.id, 1, "id")
    rows = compliance(s, 1)
    assert rows[0]["mapped"] is True
    assert rows[1]["mapped"] is False
    assert list_mappings(s, 1)[0].column_name == "id"
