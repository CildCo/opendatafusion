from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Column, Dataset, Datasource, Project
from odf.services.catalog import search_catalog


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="c1", name="c1", status=1),
               Project(id=2, code="c2", name="c2", status=1)])
    s.add_all([
        Datasource(id=1, project_id=1, name="a", kind="sqlite",
                   dsn_encrypted="x"),
        Datasource(id=2, project_id=2, name="b", kind="sqlite",
                   dsn_encrypted="x"),
    ])
    s.add_all([
        Dataset(id=1, datasource_id=1, schema_name="main",
                table_name="sales_order"),
        Dataset(id=2, datasource_id=1, schema_name="main",
                table_name="customers"),
        Dataset(id=3, datasource_id=2, schema_name="main",
                table_name="sales_secret"),
    ])
    s.add_all([
        Column(id=1, dataset_id=1, name="id", data_type="INTEGER"),
        Column(id=2, dataset_id=1, name="amount", data_type="NUMERIC"),
        Column(id=3, dataset_id=2, name="customer_name", data_type="TEXT"),
        Column(id=4, dataset_id=3, name="amount", data_type="NUMERIC"),
    ])
    s.commit()
    return s


def test_search_matches_tables_and_columns_scoped_to_project():
    s = _env()
    out = search_catalog(s, 1, "sale")
    assert [t["table"] for t in out["tables"]] == ["sales_order"]
    assert out["columns"] == []
    out = search_catalog(s, 1, "amount")
    assert out["tables"] == []
    assert len(out["columns"]) == 1
    assert out["columns"][0]["table"] == "sales_order"
    assert out["columns"][0]["column"] == "amount"
    # project 2's identically named column never leaks
    assert all(c["table"] != "sales_secret" for c in out["columns"])
    out = search_catalog(s, 1, "sale")
    assert out["tables"][0]["datasource_id"] == 1


def test_search_is_case_insensitive_and_limited():
    s = _env()
    out = search_catalog(s, 1, "CUSTOMER")
    assert [t["table"] for t in out["tables"]] == ["customers"]
    assert out["columns"][0]["column"] == "customer_name"
    assert search_catalog(s, 1, "  ") == {"tables": [], "columns": []}
    assert len(search_catalog(s, 1, "a", limit=1)["columns"]) == 1
