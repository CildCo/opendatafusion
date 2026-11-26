import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.assets.service import get_asset
from odf.db import Base
from odf.models import AssetVersion, Datasource
from odf.services.crypto import encrypt_secret
from odf.services.templates import apply_template, list_templates


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "t.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text)"))
        c.execute(text("create table orders_copy (id int, city text)"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="local", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    return s


def _draft(s, asset):
    return s.get(AssetVersion, asset.draft_version_id).content_json


def test_templates_can_be_filtered_by_type():
    models = list_templates("model")
    assert models and all(row["type"] == "model" for row in models)
    pipelines = list_templates("pipeline")
    assert [row["id"] for row in pipelines] == ["pipeline-copy"]


def test_apply_model_template_creates_draft(tmp_path):
    s = _env(tmp_path)
    out = apply_template(s, 1, "model-staging", {
        "name": "orders staging", "datasource_id": 1,
        "table": "orders", "schema_name": "main"}, "alice")
    asset = get_asset(s, out["id"])
    content = _draft(s, asset)
    assert asset.type == "model"
    assert asset.name == "orders staging"
    assert content["sql"] == "select * from orders"
    assert content["layer"] == "staging"


def test_apply_merge_template_sets_incremental(tmp_path):
    s = _env(tmp_path)
    out = apply_template(s, 1, "model-merge", {
        "name": "orders merge", "datasource_id": 1,
        "table": "orders", "schema_name": "main"}, "alice")
    content = _draft(s, get_asset(s, out["id"]))
    assert content["materialization"] == "incremental"
    assert content["incremental_strategy"] == "merge"
    assert content["unique_key"] == ["id"]


def test_apply_pipeline_template_creates_dag(tmp_path):
    s = _env(tmp_path)
    out = apply_template(s, 1, "pipeline-copy", {
        "name": "orders copy", "datasource_id": 1,
        "table": "orders", "target_datasource_id": 1,
        "target_table": "orders_copy", "pk": "id"}, "alice")
    asset = get_asset(s, out["id"])
    content = _draft(s, asset)
    assert asset.type == "pipeline"
    assert content["nodes"][0]["config"]["table"] == "orders"
    assert content["nodes"][1]["config"]["table"] == "orders_copy"


def test_invalid_table_is_rejected(tmp_path):
    s = _env(tmp_path)
    with pytest.raises(ValueError):
        apply_template(s, 1, "model-staging", {
            "name": "x", "datasource_id": 1,
            "table": "orders; drop table x"}, "alice")


def test_unknown_template_is_rejected(tmp_path):
    s = _env(tmp_path)
    with pytest.raises(ValueError):
        apply_template(s, 1, "missing", {}, "alice")


def test_apply_app_templates_creates_drafts(tmp_path):
    s = _env(tmp_path)
    approval = apply_template(s, 1, "app-approval", {"name": "Approvals"},
                              "alice")
    upload = apply_template(s, 1, "app-upload", {"name": "Files"}, "alice")
    assert get_asset(s, approval["id"]).type == "app"
    assert get_asset(s, upload["id"]).type == "app"
    assert _draft(s, get_asset(s, approval["id"]))["pages"][0][
        "components"][1]["type"] == "approval"
    assert _draft(s, get_asset(s, upload["id"]))["pages"][0][
        "components"][1]["type"] == "upload"
