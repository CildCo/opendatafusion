from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Project


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Project(id=1, code="p", name="P", status=1))
    s.commit()
    return s


def test_domains_terms_and_asset_contract():
    from odf.services.governance import (asset_governance, create_domain,
                                          create_term, list_domains,
                                          update_asset_governance)
    s = _session()
    domain = create_domain(s, 1, "交易域", "订单与支付", "alice")
    assert [row.name for row in list_domains(s, 1)] == ["交易域"]
    term = create_term(s, 1, "GMV", "成交总额", domain.id, "alice")
    assert term.domain_id == domain.id
    asset = create_asset(s, 1, "dataset", "D", {"mode": "visual"}, "u")
    out = update_asset_governance(s, 1, asset.id, domain.id, {
        "owner": "alice", "sla": "每日 08:00 前", "schema": ["id"],
        "quality": [{"kind": "not_null", "column": "id"}],
    })
    assert out["domain_name"] == "交易域"
    assert out["contract"]["sla"] == "每日 08:00 前"
    assert asset_governance(s, 1, asset.id)["domain_id"] == domain.id


def test_asset_usage_finds_references_and_runs():
    from odf.models import Job
    from odf.services.governance import asset_usage
    s = _session()
    dataset = create_asset(s, 1, "dataset", "D", {"mode": "visual"}, "u")
    metric = create_asset(s, 1, "metric", "M", {
        "dataset_id": dataset.id,
        "measure": {"agg": "count", "column": "*"},
        "dimensions": [],
    }, "u")
    dashboard = create_asset(s, 1, "dashboard", "B", {
        "widgets": [{"id": "w1", "type": "card",
                     "metric_id": metric.id, "x": 0, "y": 0, "w": 3,
                     "h": 2}],
    }, "u")
    s.add(Job(asset_id=metric.id, asset_type="metric", status="success",
              attempts=1))
    s.commit()
    usage = asset_usage(s, 1, metric.id)
    assert {row["id"] for row in usage["references"]} == {dashboard.id}
    assert usage["runs"] == 1
    assert asset_usage(s, 1, dataset.id)["reference_count"] >= 1


def test_bulk_glossary_import_upserts_csv_and_json():
    from odf.services.governance import (create_domain, create_term,
                                          import_terms, list_terms)
    s = _session()
    dom = create_domain(s, 1, "Sales", "")
    create_term(s, 1, "GMV", "old", dom.id, "alice")
    csv_text = ("term,definition,domain,owner\n"
                "GMV,new definition,Sales,bob\n"
                "ARPU,revenue per user,Sales,carol\n"
                "MISSING,x,NoSuchDomain,dave\n")
    out = import_terms(s, 1, csv_text, "csv", "editor")
    assert out["created"] == 1 and out["updated"] == 1
    assert out["skipped"] == 1
    assert out["errors"][0]["row"] == 3
    rows = {row.term: row for row in list_terms(s, 1)}
    assert rows["GMV"].definition == "new definition"
    assert rows["GMV"].owner == "bob"
    assert rows["ARPU"].domain_id == dom.id
    js = '[{"term":"ARPU","definition":"json update","domain":"Sales"}]'
    out = import_terms(s, 1, js, "json", "editor")
    assert out["updated"] == 1
    assert {row.term: row.definition for row in list_terms(s, 1)}[
        "ARPU"] == "json update"
