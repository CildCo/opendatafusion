import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.apistudio.service import preview_api
from odf.assets.service import create_asset, publish_asset
from odf.connectors.file import FileSource
from odf.db import Base
from odf.models import Alert, Datasource, Dataset, Project, QualityRule
from odf.modelstudio.service import preview_dataset, query_metric
from odf.services.crypto import encrypt_secret
from odf.services.metadata import list_tables, sync_datasource
from odf.services.quality import run_rule
from odf.settings import get_settings
from odf.workbench.service import run_query


@pytest.fixture(autouse=True)
def _file_roots(tmp_path, monkeypatch):
    monkeypatch.setenv("ODF_FILE_SOURCE_ROOTS", str(tmp_path))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="f1", name="f1", status=1))
    s.commit()
    return s


def _file_ds(s, path, did=1):
    ds = Datasource(id=did, project_id=1, name=path.stem, kind="file",
                    dsn_encrypted=encrypt_secret(str(path)))
    s.add(ds)
    s.commit()
    return ds


def _csv(tmp_path):
    p = tmp_path / "sales.csv"
    p.write_text("id,name,amount\n1,a,10\n2,b,20\n3,c,30\n",
                 encoding="utf-8")
    return p


def _xlsx(tmp_path):
    p = tmp_path / "orders.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["id", "city", "amount"])
    ws.append([1, "上海", 5])
    ws.append([2, "北京", 7])
    wb.save(p)
    return p


def _dataset(s, dsid, table, select=None):
    a = create_asset(s, 1, "dataset", "D", {
        "mode": "visual", "query": {"datasource_id": dsid, "table": table,
                                    "select": select or [{"column": "id"},
                                                         {"column": "name"}],
                                    "limit": 100},
        "params": [], "sql": None, "auth": None}, "admin", enabled=False)
    publish_asset(s, a.id, "admin")
    return a


def test_csv_sync_preview_and_workbench(tmp_path):
    s = _session()
    ds = _file_ds(s, _csv(tmp_path))
    assert sync_datasource(s, ds.id) == 1
    tables = list_tables(s, ds.id)
    assert tables[0]["schema"] == "file"
    assert tables[0]["table"] == "sales"
    assert [c["name"] for c in tables[0]["columns"]] == \
        ["id", "name", "amount"]
    a = _dataset(s, ds.id, "sales")
    out = preview_dataset(s, a.id, published_only=True)
    assert out["row_count"] == 3
    assert out["rows"][1] == {"id": 2, "name": "b"}
    wb = run_query(s, 1, ds.id,
                   'select name from "file"."sales" order by id', actor="u")
    assert wb["columns"] == ["name"]
    assert [r["name"] for r in wb["rows"]] == ["a", "b", "c"]
    assert wb["truncated"] is False


def test_api_and_metric_read_file(tmp_path):
    s = _session()
    ds = _file_ds(s, _csv(tmp_path))
    sync_datasource(s, ds.id)
    ds_asset = _dataset(s, ds.id, "sales",
                        [{"column": "id"}, {"column": "name"},
                         {"column": "amount"}])
    api = create_asset(s, 1, "api", "A", {
        "mode": "visual",
        "query": {"datasource_id": ds.id, "table": "sales",
                  "select": [{"column": "name"}, {"column": "amount"}],
                  "filters": [{"column": "amount", "op": ">",
                               "param": "min"}],
                  "limit": 100},
        "sql": None,
        "params": [{"name": "min", "type": "number", "required": True}],
        "auth": {"type": "aksk", "rate_limit_per_min": 60}},
        "admin", enabled=False)
    publish_asset(s, api.id, "admin")
    out = preview_api(s, api.id, {"min": 15})
    assert out["row_count"] == 2
    assert out["rows"][0] == {"name": "b", "amount": 20}
    metric = create_asset(s, 1, "metric", "M", {
        "dataset_id": ds_asset.id,
        "measure": {"agg": "sum", "column": "amount", "as": "value"},
        "dimensions": ["name"], "filters": [],
        "format": {"type": "number"}}, "admin", enabled=False)
    publish_asset(s, metric.id, "admin")
    m = query_metric(s, metric.id)
    assert {r["name"]: r["value"] for r in m["rows"]} == \
        {"a": 10, "b": 20, "c": 30}


def test_excel_sync_and_query(tmp_path):
    s = _session()
    ds = _file_ds(s, _xlsx(tmp_path))
    assert sync_datasource(s, ds.id) == 1
    info = list_tables(s, ds.id)[0]
    assert info["table"] == "orders"
    assert [c["name"] for c in info["columns"]] == ["id", "city", "amount"]
    out = run_query(s, 1, ds.id,
                    'select city, amount from "file"."orders" order by id')
    assert out["rows"] == [{"city": "上海", "amount": 5},
                           {"city": "北京", "amount": 7}]


def test_file_source_cursor(tmp_path):
    s = _session()
    ds = _file_ds(s, _csv(tmp_path))
    src = FileSource(ds, {"source_table": "sales", "cursor_column": "id",
                          "pk": "id"})
    rows, cur = src.read(None, 2)
    assert [r["id"] for r in rows] == [1, 2]
    assert cur
    rows, cur = src.read(cur, 2)
    assert [r["id"] for r in rows] == [3]
    assert cur


def test_file_validation(tmp_path, monkeypatch):
    s = _session()
    ds = _file_ds(s, tmp_path / "nope.csv")
    with pytest.raises(ValueError):
        sync_datasource(s, ds.id)
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    secret = tmp_path / "secret.csv"
    secret.write_text("id\n1\n")
    monkeypatch.setenv("ODF_FILE_SOURCE_ROOTS", str(allowed))
    get_settings.cache_clear()
    ds_out = _file_ds(s, secret, 4)
    with pytest.raises(ValueError):
        sync_datasource(s, ds_out.id)
    monkeypatch.setenv("ODF_FILE_SOURCE_ROOTS", str(tmp_path))
    get_settings.cache_clear()
    bad = tmp_path / "x.xlsx2"
    bad.write_text("nope")
    ds2 = _file_ds(s, bad, 2)
    with pytest.raises(ValueError):
        sync_datasource(s, ds2.id)
    corrupt = tmp_path / "corrupt.xlsx"
    corrupt.write_bytes(b"not a zip")
    ds_bad = _file_ds(s, corrupt, 5)
    with pytest.raises(ValueError):
        sync_datasource(s, ds_bad.id)
    wr = tmp_path / "drop.csv"
    wr.write_text("id\n1\n")
    ds3 = _file_ds(s, wr, 3)
    sync_datasource(s, ds3.id)
    with pytest.raises(ValueError):
        run_query(s, 1, ds3.id,
                  "select * from read_csv_auto('/etc/passwd')")


def test_schema_drift_raises_alert(tmp_path):
    s = _session()
    url = "sqlite:///" + str(tmp_path / "drift.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table t (id int, v text)"))
    ds = Datasource(id=9, project_id=1, name="drift", kind="sqlite",
                    dsn_encrypted=encrypt_secret(url))
    s.add(ds)
    s.commit()
    sync_datasource(s, 9)
    with raw.begin() as c:
        c.execute(text("alter table t add column extra int"))
    assert sync_datasource(s, 9) == 1
    alert = s.query(Alert).filter_by(project_id=1).first()
    assert alert is not None
    assert alert.title == "schema drift: main.t"
    assert alert.detail_json["added"] == ["extra"]
    assert alert.severity == "warning"
    # unchanged schema does not create another alert
    sync_datasource(s, 9)
    assert s.query(Alert).filter_by(project_id=1).count() == 1


def test_quality_rules_run_on_file_source(tmp_path):
    s = _session()
    ds = _file_ds(s, _csv(tmp_path))
    sync_datasource(s, ds.id)
    dataset = s.query(Dataset).filter_by(datasource_id=ds.id).first()
    rule = QualityRule(project_id=1, dataset_id=dataset.id, name="rows",
                       kind="row_count", config_json={"min": 5})
    ok_rule = QualityRule(project_id=1, dataset_id=dataset.id, name="notnull",
                          kind="not_null", column_name="name")
    s.add_all([rule, ok_rule])
    s.commit()
    assert run_rule(s, rule.id).status == "fail"
    assert run_rule(s, ok_rule.id).status == "pass"
