import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import (Alert, Asset, Column, Dataset, Datasource, Domain,
                        GlossaryTerm, ProjectMember, User)
from odf.services.alerts import (add_alert_note, alert_assignees,
                                 assign_alert, list_alert_notes)
from odf.services.catalog import (dataset_detail, link_column_term,
                                  search_catalog, term_columns,
                                  unlink_column_term)
from odf.services.favorites import (add_favorite, is_favorite,
                                    list_favorites, remove_favorite)


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
    s.add(Domain(id=1, project_id=1, name="Sales"))
    s.add(Dataset(id=1, datasource_id=1, schema_name="main",
                  table_name="orders", domain_id=1))
    s.add(Dataset(id=2, datasource_id=2, schema_name="main",
                  table_name="secret"))
    s.add(Column(id=1, dataset_id=1, name="amount", data_type="INTEGER"))
    s.add(GlossaryTerm(id=1, project_id=1, domain_id=1, term="成交额",
                       definition="订单金额"))
    s.add(Asset(id=1, project_id=1, type="dashboard", key="k1",
                name="Sales", owner="admin"))
    s.add(Asset(id=2, project_id=2, type="dashboard", key="k2",
                name="Other", owner="bob"))
    s.add(User(id=1, username="alice", password_hash="x", role="editor",
               active=True))
    s.add(User(id=2, username="bob", password_hash="x", role="editor",
               active=True))
    s.add(ProjectMember(id=1, project_id=1, user_id=1, role="editor"))
    s.add(Alert(id=1, project_id=1, severity="warning", title="freshness",
                detail_json={}, status="open"))
    s.commit()
    return s


def test_favorite_asset_and_table_routes():
    s = _env()
    item = add_favorite(s, 1, 1, "dashboard", 1)
    assert item["route"] == "/dashboards/1/run"
    assert is_favorite(s, 1, 1, "dashboard", 1)
    table = add_favorite(s, 1, 1, "table", 1)
    assert table["route"] == "/catalog/1"
    assert table["label"] == "main.orders"
    assert len(list_favorites(s, 1, 1)) == 2
    assert remove_favorite(s, 1, 1, "dashboard", 1)
    assert not is_favorite(s, 1, 1, "dashboard", 1)
    with pytest.raises(ValueError):
        add_favorite(s, 1, 1, "dashboard", 2)
    with pytest.raises(ValueError):
        add_favorite(s, 1, 1, "table", 2)
    with pytest.raises(ValueError):
        add_favorite(s, 2, 1, "dashboard", 1)


def test_alert_assignment_and_notes():
    s = _env()
    a = assign_alert(s, 1, 1, "alice", "admin")
    assert a.assigned_to == "alice"
    assert alert_assignees(s, 1) == ["alice"]
    note = add_alert_note(s, 1, 1, "alice", "  checking upstream  ")
    assert note.body == "checking upstream"
    assert list_alert_notes(s, 1, 1)[0].actor == "alice"
    with pytest.raises(ValueError):
        assign_alert(s, 1, 1, "bob", "admin")
    with pytest.raises(ValueError):
        assign_alert(s, 2, 1, "alice", "admin")


def test_column_term_links_and_search():
    s = _env()
    link = link_column_term(s, 1, 1, "amount", 1, "admin")
    assert link["term"] == "成交额"
    detail = dataset_detail(s, 1, 1)
    amount = next(c for c in detail["columns"] if c["name"] == "amount")
    assert amount["terms"] == [{"id": 1, "term": "成交额"}]
    out = search_catalog(s, 1, "成交额")
    assert out["tables"][0]["id"] == 1
    assert out["tables"][0]["matched_terms"] == [
        {"term": "成交额", "column": "amount"}]
    assert term_columns(s, 1, 1)[0]["column"] == "amount"
    assert unlink_column_term(s, 1, 1, "amount", 1)
    assert dataset_detail(s, 1, 1)["columns"][0]["terms"] == []
    with pytest.raises(ValueError):
        link_column_term(s, 1, 1, "missing", 1, "admin")
    with pytest.raises(ValueError):
        link_column_term(s, 2, 2, "amount", 1, "admin")
