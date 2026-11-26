import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Column, Dataset, Datasource, Project
from odf.services.catalog import dataset_detail
from odf.services.external_metadata import import_external


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.commit()
    return s


def test_import_dbt_manifest_and_catalog_detail():
    s = _env()
    manifest = {
        "metadata": {"project_name": "analytics"},
        "nodes": {
            "model.analytics.orders": {
                "resource_type": "model", "name": "orders",
                "schema": "mart", "description": "Orders model",
                "columns": {"id": {"data_type": "integer",
                                   "description": "primary key"},
                            "amount": {"data_type": "numeric"}},
            },
            "test.analytics.not_null": {"resource_type": "test"},
        },
    }
    out = import_external(s, 1, "dbt", json.dumps(manifest), "admin")
    assert out["tables"] == 1 and out["columns"] == 2
    ds = s.query(Datasource).filter_by(kind="dbt").one()
    assert ds.name == "dbt analytics"
    row = s.query(Dataset).filter_by(table_name="orders").one()
    assert row.description == "Orders model"
    assert [c.name for c in s.query(Column).filter_by(dataset_id=row.id)] == [
        "id", "amount"]
    detail = dataset_detail(s, row.id, 1)
    assert detail["external"] is True
    assert detail["description"] == "Orders model"
    assert detail["columns"][0]["description"] == "primary key"


def test_import_bi_metadata_and_validation():
    s = _env()
    payload = {"tool": "tableau", "reports": [{
        "name": "Sales report", "schema": "finance", "owner": "alice",
        "description": "Monthly sales",
        "columns": [{"name": "month", "type": "date"},
                    {"name": "revenue", "type": "number"}]}]}
    out = import_external(s, 1, "bi", json.dumps(payload), "admin")
    assert out["tables"] == 1 and out["columns"] == 2
    ds = s.query(Datasource).filter_by(kind="bi").one()
    assert ds.name == "bi tableau"
    row = s.query(Dataset).filter_by(table_name="Sales report").one()
    assert row.owner == "alice"
    try:
        import_external(s, 1, "other", "{}", "admin")
    except ValueError as e:
        assert "source" in str(e)
    else:
        raise AssertionError("invalid source must fail")
