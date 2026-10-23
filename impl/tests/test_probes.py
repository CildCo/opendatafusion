from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from odf.main import app


def test_live_and_ready():
    c = TestClient(app)
    assert c.get("/livez").status_code == 200
    r = c.get("/readyz")
    assert r.status_code == 200 and r.json()["database"] == "ok"
    assert c.get("/healthz").status_code == 200


def test_ready_reports_database_failure(monkeypatch):
    import odf.db
    broken = create_engine("sqlite:////nonexistent-dir/odf.db")
    monkeypatch.setattr(odf.db, "engine", broken)
    r = TestClient(app).get("/readyz")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"
