import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import (Column, ColumnPolicy, Dataset, DatasetTag, Datasource,
                        Domain, LineageEdge, Tag)
from odf.services.catalog import (add_comment, dataset_detail, lineage,
                                  list_comments, list_datasets,
                                  search_catalog, set_comment_status)


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _env():
    s = _session()
    s.add(Datasource(id=1, project_id=1, name="src", kind="sqlite",
                     dsn_encrypted="x"))
    s.add(Datasource(id=2, project_id=2, name="other", kind="sqlite",
                     dsn_encrypted="x"))
    s.add(Domain(id=1, project_id=1, name="Sales", description="",
                 owner="a"))
    s.add(Dataset(id=1, datasource_id=1, schema_name="main",
                  table_name="orders", domain_id=1))
    s.add(Dataset(id=2, datasource_id=2, schema_name="main",
                  table_name="secret"))
    s.add(Column(id=1, dataset_id=1, name="customer_email",
                 data_type="VARCHAR"))
    s.add(Column(id=2, dataset_id=1, name="amount", data_type="INTEGER"))
    s.add(ColumnPolicy(id=1, project_id=1, datasource_id=1,
                       schema_name="main", table_name="orders",
                       column_name="customer_email",
                       classification="pii", mask_type="redact",
                       exempt_roles_json=["admin"], created_by="admin"))
    s.commit()
    return s


def test_detail_includes_domain_policies_and_comments():
    s = _env()
    detail = dataset_detail(s, 1, 1)
    assert detail["domain_name"] == "Sales"
    email = next(c for c in detail["columns"] if c["name"] == "customer_email")
    assert email["classification"] == "pii"
    assert email["exempt_roles"] == ["admin"]
    assert detail["comments"] == {"open": 0, "total": 0}


def test_list_datasets_adds_domain():
    s = _env()
    rows = list_datasets(s, 1)
    assert rows[0]["domain_id"] == 1
    assert rows[0]["domain_name"] == "Sales"


def test_comments_add_list_and_resolve():
    s = _env()
    c = add_comment(s, 1, 1, "alice", "  please document  ")
    assert c["body"] == "please document"
    assert c["status"] == "open"
    assert list_comments(s, 1, 1)[0]["id"] == c["id"]
    done = set_comment_status(s, 1, c["id"], "admin", "resolved")
    assert done["status"] == "resolved"
    assert done["resolved_by"] == "admin"
    assert list_comments(s, 1, 1, "open") == []
    assert dataset_detail(s, 1, 1)["comments"]["open"] == 0
    reopened = set_comment_status(s, 1, c["id"], "admin", "open")
    assert reopened["resolved_at"] is None


def test_comments_reject_blank_and_cross_project():
    s = _env()
    with pytest.raises(ValueError):
        add_comment(s, 1, 1, "alice", "   ")
    with pytest.raises(ValueError):
        add_comment(s, 1, 2, "alice", "cross")
    c = add_comment(s, 1, 1, "alice", "note")
    with pytest.raises(ValueError):
        set_comment_status(s, 2, c["id"], "bob", "resolved")


def test_lineage_direction_and_depth():
    s = _env()
    s.add(LineageEdge(project_id=1, from_type="table", from_id="1:raw",
                      from_ref="1:raw", to_type="table", to_id="1:mid",
                      to_ref="1:mid"))
    s.add(LineageEdge(project_id=1, from_type="table", from_id="1:mid",
                      from_ref="1:mid", to_type="table", to_id="1:mart",
                      to_ref="1:mart"))
    s.add(LineageEdge(project_id=1, from_type="table", from_id="1:mart",
                      from_ref="1:mart", to_type="model", to_id="7",
                      to_ref="model:7"))
    s.commit()
    down = lineage(s, 1, "1:mid", 1, "downstream")
    assert down["nodes"] == ["1:mart", "1:mid"]
    up = lineage(s, 1, "1:mid", 2, "upstream")
    assert up["nodes"] == ["1:mid", "1:raw"]
    both = lineage(s, 1, "1:mid", 5, "both")
    assert "model:7" in both["nodes"]
    assert both["node_types"]["model:7"] == "model"


def test_search_matches_columns_and_tags():
    s = _env()
    s.add(Tag(id=1, project_id=1, name="customer"))
    s.commit()
    s.add(DatasetTag(dataset_id=1, tag_id=1))
    s.commit()
    out = search_catalog(s, 1, "customer")
    assert out["tables"][0]["id"] == 1
    assert "customer_email" in out["tables"][0]["matched_columns"]
    assert out["tables"][0]["matched_tags"] == ["customer"]
    assert out["tags"][0]["name"] == "customer"
    assert "secret" not in [t["table"] for t in out["tables"]]
