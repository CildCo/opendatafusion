from fastapi.testclient import TestClient

from odf.main import app


def test_metrics_endpoint():
    r = TestClient(app).get("/metrics")
    assert r.status_code == 200
    assert "odf_requests_total" in r.text
    assert "odf_request_seconds_count" in r.text
