import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset, publish_asset
from odf.db import Base
from odf.models import Datasource
from odf.services.contracts import check_asset, generate_contract
from odf.services.crypto import encrypt_secret
from odf.services.governance import update_asset_governance
from odf.transform.service import materialize_model


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "c.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders "
                       "(id int, city text, amount int)"))
        c.execute(text("insert into orders values (1,'a',10)"))
        c.execute(text("create table q (id int, city text)"))
        c.execute(text("insert into q values (1,'a'),(2,'a'),(3,null)"))
        c.execute(text("create table events "
                       "(id int, updated_at text)"))
        c.execute(text("insert into events values "
                       "(1,'2026-11-20T08:00:00+00:00')"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s, url


def _dataset(s, name="orders", table="orders"):
    return create_asset(
        s, 1, "dataset", name,
        {"query": {"datasource_id": 1, "table": table}}, "admin")


def _model(s, name, sql, columns=None):
    return create_asset(
        s, 1, "model", name,
        {"datasource_id": 1, "sql": sql, "materialization": "table",
         "schema": "main", "unique_key": [], "layer": "staging",
         "description": "", "tests": [], "columns": columns or []},
        "admin")


def test_generate_contract_from_dataset_columns(tmp_path):
    s, _ = _env(tmp_path)
    asset = _dataset(s)
    contract = generate_contract(s, 1, asset.id)
    names = [item["name"] for item in contract["schema"]]
    assert names == ["id", "city", "amount"]


def test_check_passes_for_matching_schema(tmp_path):
    s, _ = _env(tmp_path)
    asset = _dataset(s)
    generate_contract(s, 1, asset.id)
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is True
    assert out["target"] == "orders"
    assert out["issues"] == []


def test_missing_and_extra_columns_are_reported(tmp_path):
    s, _ = _env(tmp_path)
    asset = _dataset(s)
    update_asset_governance(
        s, 1, asset.id, contract={
            "schema": [{"name": "id", "type": "int"},
                       {"name": "ghost", "type": "text"}],
            "allow_extra": False})
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is False
    kinds = {(item["kind"], item["column"]) for item in out["issues"]}
    assert ("missing", "ghost") in kinds
    assert ("unexpected", "city") in kinds


def test_type_mismatch_is_reported(tmp_path):
    s, _ = _env(tmp_path)
    asset = _dataset(s)
    update_asset_governance(
        s, 1, asset.id,
        contract={"schema": [{"name": "amount", "type": "text"}]})
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is False
    assert out["issues"][0]["kind"] == "type"
    assert out["issues"][0]["column"] == "amount"


def test_model_run_fails_when_enforced_contract_breaks(tmp_path):
    s, _ = _env(tmp_path)
    asset = _model(s, "m", "select id, city from orders")
    publish_asset(s, asset.id, "admin")
    materialize_model(s, asset.id)
    update_asset_governance(
        s, 1, asset.id,
        contract={"enforce": True,
                  "schema": [{"name": "id"}, {"name": "city"},
                             {"name": "amount"}]})
    with pytest.raises(ValueError) as error:
        materialize_model(s, asset.id)
    assert "contract" in str(error.value)


def test_freshness_contract_passes_for_recent_data(tmp_path):
    from datetime import datetime, timezone
    s, url = _env(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("update events set updated_at = :v"), {"v": now})
    raw.dispose()
    asset = _dataset(s, name="events", table="events")
    update_asset_governance(
        s, 1, asset.id,
        contract={"freshness": {"column": "updated_at", "max_hours": 24}})
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is True


def test_freshness_contract_reports_stale_data(tmp_path):
    s, _ = _env(tmp_path)
    asset = _dataset(s, name="events", table="events")
    update_asset_governance(
        s, 1, asset.id,
        contract={"freshness": {"column": "updated_at", "max_hours": 24}})
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is False
    assert out["issues"][0]["kind"] == "stale"
    assert out["issues"][0]["column"] == "updated_at"


def test_invalid_freshness_config_is_rejected(tmp_path):
    s, _ = _env(tmp_path)
    asset = _dataset(s, name="events", table="events")
    with pytest.raises(ValueError):
        update_asset_governance(
            s, 1, asset.id,
            contract={"freshness": {"column": "bad name", "max_hours": 24}})
    with pytest.raises(ValueError):
        update_asset_governance(
            s, 1, asset.id,
            contract={"freshness": {"column": "updated_at", "max_hours": 0}})


def _quality_dataset(s, table="q", name="q"):
    return create_asset(
        s, 1, "dataset", name,
        {"query": {"datasource_id": 1, "table": table}}, "admin")


def test_quality_not_null_and_unique(tmp_path):
    s, _ = _env(tmp_path)
    asset = _quality_dataset(s)
    update_asset_governance(s, 1, asset.id, contract={
        "quality": [{"kind": "not_null", "column": "city"},
                    {"kind": "unique", "column": "city"}]})
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is False
    kinds = {(item["kind"], item["column"]) for item in out["issues"]}
    assert ("quality", "city") in kinds
    assert len(out["issues"]) == 2


def test_quality_accepted_values_and_null_pct(tmp_path):
    s, _ = _env(tmp_path)
    asset = _quality_dataset(s)
    update_asset_governance(s, 1, asset.id, contract={
        "quality": [{"kind": "accepted_values", "column": "city",
                     "values": ["b"]},
                    {"kind": "max_null_pct", "column": "city",
                     "max_null_pct": 10}]})
    out = check_asset(s, 1, asset.id)
    assert out["ok"] is False
    assert len(out["issues"]) == 2


def test_quality_custom_sql(tmp_path):
    s, _ = _env(tmp_path)
    asset = _quality_dataset(s)
    update_asset_governance(s, 1, asset.id, contract={
        "quality": [{"kind": "sql",
                     "sql": "select count(*) from q where id > 100"}]})
    assert check_asset(s, 1, asset.id)["ok"] is True
    update_asset_governance(s, 1, asset.id, contract={
        "quality": [{"kind": "sql",
                     "sql": "select count(*) from q where id > 1"}]})
    assert check_asset(s, 1, asset.id)["ok"] is False


def test_invalid_quality_check_is_rejected(tmp_path):
    s, _ = _env(tmp_path)
    asset = _quality_dataset(s)
    with pytest.raises(ValueError):
        update_asset_governance(s, 1, asset.id, contract={
            "quality": [{"kind": "sql", "sql": "delete from q"}]})
    with pytest.raises(ValueError):
        update_asset_governance(s, 1, asset.id, contract={
            "quality": [{"kind": "unknown", "column": "id"}]})


def test_contract_check_rejects_unsupported_asset(tmp_path):
    s, _ = _env(tmp_path)
    asset = create_asset(s, 1, "metric", "m1",
                         {"dataset_id": 1, "measure": {}}, "admin")
    with pytest.raises(ValueError):
        check_asset(s, 1, asset.id)
