import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.lakehouse.properties import build_spec
from odf.main import app
from odf.models import Datasource, EngineJob, User
from odf.services.auth import create_token
from odf.services.crypto import encrypt_secret


def _settings():
    return SimpleNamespace(
        spark_image="odf/spark-iceberg:3.5.1",
        lakehouse_property_script="local:///opt/odf-spark-jars/set_properties.py",
    )


def _user(uid, role, project_id=1):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="lp_%d" % uid, password_hash="x",
                        role=role, active=True)
            s.add(user)
        else:
            user.role = role
            user.active = True
        s.commit()
    return {"Authorization": "Bearer " + create_token(uid, project_id)}


def _ds(project_id=1):
    with SessionLocal() as s:
        ds = Datasource(project_id=project_id,
                        name="lp-%s" % uuid.uuid4().hex[:6], kind="trino",
                        dsn_encrypted=encrypt_secret(
                            "trino://odf@trino:8080/iceberg/demo"))
        s.add(ds)
        s.commit()
        s.refresh(ds)
        return ds.id


class FakeClient:
    catalog = "iceberg"
    schema = ""


class FakeSpark:
    def __init__(self):
        self.submitted = []

    def submit(self, spec):
        self.submitted.append(spec)
        return spec.name


@pytest.fixture()
def session():
    with SessionLocal() as s:
        yield s


def test_build_spec_renders_arguments():
    spec = build_spec("iceberg.odf_p1.events",
                      {"gc.enabled": "true", "count": 3, "flag": False},
                      _settings())
    assert spec["image"] == "odf/spark-iceberg:3.5.1"
    assert spec["main_application_file"] == (
        "local:///opt/odf-spark-jars/set_properties.py")
    assert spec["args"] == [
        "iceberg.odf_p1.events",
        "gc.enabled='true'",
        "count='3'",
        "flag='false'",
    ]
    assert spec["executor_instances"] == 1


def test_build_spec_doubles_quotes_in_values():
    spec = build_spec("iceberg.odf_p1.events", {"comment": "it's fine"},
                      _settings())
    assert spec["args"] == ["iceberg.odf_p1.events", "comment='it''s fine'"]


@pytest.mark.parametrize("table", [
    "events",
    "iceberg.events",
    "iceberg.odf_p1.events.extra",
    "iceberg..events",
    "iceberg.odf-p1.events",
    "iceberg.odf_p1.events; drop table x",
])
def test_build_spec_rejects_bad_identifiers(table):
    with pytest.raises(ValueError, match="catalog.schema.table"):
        build_spec(table, {"gc.enabled": "true"}, _settings())


@pytest.mark.parametrize("name", ["", "1abc", "gc enabled", "gc/xx", None])
def test_build_spec_rejects_bad_property_names(name):
    with pytest.raises(ValueError, match="property name"):
        build_spec("iceberg.odf_p1.events", {name: "true"}, _settings())


@pytest.mark.parametrize("value", [None, ["a"], {"a": 1}])
def test_build_spec_rejects_non_scalar_values(value):
    with pytest.raises(ValueError, match="scalars"):
        build_spec("iceberg.odf_p1.events", {"gc.enabled": value}, _settings())


def test_build_spec_requires_properties():
    with pytest.raises(ValueError, match="at least one property"):
        build_spec("iceberg.odf_p1.events", {}, _settings())


def test_properties_route_submits_a_job(monkeypatch, session):
    datasource_id = _ds()
    spark = FakeSpark()
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda ds: FakeClient())
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        lambda: spark)

    response = TestClient(app).post(
        "/api/v1/lakehouse/tables/events/properties",
        headers=_user(981, "editor"),
        json={"datasource_id": datasource_id,
              "properties": {"gc.enabled": "true"}})

    assert response.status_code == 201
    body = response.json()
    assert body["table"] == "iceberg.odf_p1.events"
    assert body["properties"] == {"gc.enabled": "true"}
    assert spark.submitted[0].name == body["name"]
    assert spark.submitted[0].args == [
        "iceberg.odf_p1.events", "gc.enabled='true'"]
    job = session.get(EngineJob, body["job_id"])
    assert job.spec_json["args"] == spark.submitted[0].args


def test_properties_route_uses_the_given_schema(monkeypatch, session):
    datasource_id = _ds()
    spark = FakeSpark()
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda ds: FakeClient())
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        lambda: spark)

    response = TestClient(app).post(
        "/api/v1/lakehouse/tables/events/properties",
        headers=_user(982, "editor"),
        json={"datasource_id": datasource_id, "schema_name": "analytics",
              "properties": {"gc.enabled": "true"}})

    assert response.status_code == 201
    assert response.json()["table"] == "iceberg.analytics.events"


def test_properties_route_rejects_foreign_datasource():
    datasource_id = _ds(project_id=2)
    response = TestClient(app).post(
        "/api/v1/lakehouse/tables/events/properties",
        headers=_user(983, "editor", 1),
        json={"datasource_id": datasource_id,
              "properties": {"gc.enabled": "true"}})
    assert response.status_code == 404


def test_properties_route_rejects_bad_properties(monkeypatch, session):
    datasource_id = _ds()
    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda ds: FakeClient())
    response = TestClient(app).post(
        "/api/v1/lakehouse/tables/events/properties",
        headers=_user(984, "editor"),
        json={"datasource_id": datasource_id,
              "properties": {"gc enabled": "true"}})
    assert response.status_code == 400


def test_properties_route_hides_submission_errors(monkeypatch, session):
    datasource_id = _ds()

    class Boom:
        def submit(self, spec):
            raise RuntimeError("internal detail: kube refused")

    monkeypatch.setattr("odf.lakehouse.api.client_for_datasource",
                        lambda ds: FakeClient())
    monkeypatch.setattr("odf.services.engine_jobs._spark_engine",
                        lambda: Boom())

    response = TestClient(app).post(
        "/api/v1/lakehouse/tables/events/properties",
        headers=_user(985, "editor"),
        json={"datasource_id": datasource_id,
              "properties": {"gc.enabled": "true"}})

    assert response.status_code == 503
    assert "internal detail" not in response.text
