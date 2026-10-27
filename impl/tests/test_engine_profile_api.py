import uuid
from types import SimpleNamespace

from fastapi.testclient import TestClient

from odf.db import SessionLocal
from odf.main import app
from odf.models import User
from odf.services.auth import create_token


def _settings(**overrides):
    values = dict(
        lakehouse_enabled=True,
        lakehouse_catalog="iceberg",
        lakehouse_uri="http://nessie:19120/iceberg",
        lakehouse_warehouse="warehouse",
        lakehouse_s3_endpoint="http://s3:8333",
        lakehouse_s3_region="us-east-1",
        spark_image="odf/spark-iceberg:3.5.1",
        spark_jars="",
        k8s_allowed_images="apache/spark,flink,odf/spark",
        engine_sql_write_enabled=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def _headers(uid=941):
    with SessionLocal() as s:
        user = s.get(User, uid)
        if not user:
            user = User(id=uid, username="prof_%s" % uuid.uuid4().hex[:6],
                        password_hash="x", role="viewer", active=True)
            s.add(user)
        else:
            user.role = "viewer"
            user.active = True
        s.commit()
    return {"Authorization": "Bearer " + create_token(uid, 1)}


def test_profiles_requires_authentication():
    assert TestClient(app).get("/api/v1/engine/profiles").status_code == 401


def test_profiles_returns_effective_spark_profile(monkeypatch):
    monkeypatch.setattr("odf.api.engine.get_settings", lambda: _settings())
    response = TestClient(app).get("/api/v1/engine/profiles",
                                   headers=_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["spark"]["image"] == "odf/spark-iceberg:3.5.1"
    assert body["spark"]["spark_conf"]["spark.sql.catalog.iceberg.type"] == \
        "rest"
    assert body["lakehouse_enabled"] is True


def test_profiles_reports_disabled_lakehouse(monkeypatch):
    monkeypatch.setattr("odf.api.engine.get_settings",
                        lambda: _settings(lakehouse_enabled=False))
    response = TestClient(app).get("/api/v1/engine/profiles",
                                   headers=_headers(942))
    assert response.status_code == 200
    body = response.json()
    assert body["lakehouse_enabled"] is False
    assert body["spark"]["spark_conf"] == {}
