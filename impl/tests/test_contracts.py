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


def test_contract_check_rejects_unsupported_asset(tmp_path):
    s, _ = _env(tmp_path)
    asset = create_asset(s, 1, "metric", "m1",
                         {"dataset_id": 1, "measure": {}}, "admin")
    with pytest.raises(ValueError):
        check_asset(s, 1, asset.id)
