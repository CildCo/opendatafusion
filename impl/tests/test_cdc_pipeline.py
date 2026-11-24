import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from odf.cdc.pipeline import build_pipeline, topic_for
from odf.db import Base
from odf.models import CdcSource, Datasource
from odf.services.crypto import encrypt_secret


def _env(tmp_path):
    url = "sqlite:///" + str(tmp_path / "sink.db")
    raw = create_engine(url)
    with raw.begin() as c:
        c.execute(text("create table orders (id int, city text)"))
        c.execute(text("create table customers (id int, name text)"))
    raw.dispose()
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Datasource(id=1, project_id=1, name="stream", kind="kafka",
                     dsn_encrypted=encrypt_secret("kafka://localhost:9092")))
    s.add(Datasource(id=2, project_id=1, name="sink", kind="sqlite",
                     dsn_encrypted=encrypt_secret(url)))
    s.commit()
    source = CdcSource(project_id=1, name="pg", connector_name="odf-pg",
                       config_json={"table_list": "public.orders,"
                                                  "public.customers",
                                    "topic_prefix": "odf"})
    return s, source


def test_topic_naming_matches_debezium(source=None):
    source = CdcSource(project_id=1, name="pg",
                       config_json={"topic_prefix": "shop"})
    assert topic_for(source, "public.orders") == "shop.public.orders"


def test_build_pipeline_creates_one_branch_per_table(tmp_path):
    s, source = _env(tmp_path)
    out = build_pipeline(s, 1, source, 1, 2, actor="alice")
    assert out["topics"] == ["odf.public.orders", "odf.public.customers"]
    from odf.assets.service import get_asset
    asset = get_asset(s, out["id"])
    content = s.get(__import__("odf.models", fromlist=["AssetVersion"])
                    .AssetVersion, asset.draft_version_id).content_json
    nodes = {node["id"]: node for node in content["nodes"]}
    assert nodes["cdc_1"]["config"]["debezium"] is True
    assert nodes["cdc_1"]["config"]["cdc_delete"] is True
    assert nodes["sink_1"]["config"]["mode"] == "cdc"
    assert nodes["cdc_1"]["config"]["table"] == "odf.public.orders"
    assert nodes["sink_1"]["config"]["table"] == "orders"
    assert len(content["edges"]) == 2


def test_generation_requires_kafka_datasource(tmp_path):
    s, source = _env(tmp_path)
    with pytest.raises(ValueError):
        build_pipeline(s, 1, source, 2, 2)


def test_generation_requires_subscribed_tables(tmp_path):
    s, source = _env(tmp_path)
    source.config_json = {"table_list": "", "topic_prefix": "odf"}
    with pytest.raises(ValueError):
        build_pipeline(s, 1, source, 1, 2)


def test_invalid_table_is_rejected(tmp_path):
    s, source = _env(tmp_path)
    source.config_json = {"table_list": "public.orders;drop", "topic_prefix": "odf"}
    with pytest.raises(ValueError):
        build_pipeline(s, 1, source, 1, 2)
