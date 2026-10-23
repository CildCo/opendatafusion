from fastapi.testclient import TestClient

from odf.api.metrics import inc
from odf.main import app


def test_metrics_and_request_id():
    inc("test_counter_total", status="ok")
    c = TestClient(app)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "odf_test_counter_total{status=\"ok\"} 1" in r.text
    assert "odf_requests_total" in r.text
    assert r.headers.get("X-Request-Id")


def test_histogram_and_route_template_metrics():
    from odf.db import SessionLocal
    from odf.models import User
    from odf.services.auth import create_token
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="obs", password_hash="x", role="admin",
                     active=True)
            s.add(u)
        u.active = True
        s.commit()
    c = TestClient(app)
    token = create_token(1, 1)
    assert c.get("/api/v1/pipelines/999/cursors",
                 headers={"Authorization": "Bearer " + token}
                 ).status_code == 404
    text = c.get("/metrics").text
    assert "odf_request_duration_seconds_bucket" in text
    assert 'path="/api/v1/pipelines/{asset_id}/cursors"' in text


def test_queue_gauges():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from odf.api.metrics import _queue_gauges
    from odf.db import Base
    from odf.models import Alert, Job, Project, WebhookDelivery
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(Project(id=1, code="m", name="m", status=1))
    s.add_all([Job(status="queued"), Job(status="queued"),
               Job(status="running"),
               WebhookDelivery(subscription_id=1, project_id=1,
                               event="asset.published", status="pending"),
               Alert(project_id=1, severity="warning", title="x",
                     status="open")])
    s.commit()
    gauges = dict(_queue_gauges(s))
    assert gauges['odf_queue_depth{status="queued"}'] == 2
    assert gauges['odf_queue_depth{status="running"}'] == 1
    assert gauges["odf_webhook_pending"] == 1
    assert gauges["odf_alerts_open"] == 1


def test_otel_disabled_by_default():
    from odf.observability import configure_observability
    assert configure_observability(app) is False


def test_sqlalchemy_spans_are_emitted():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter)
    from sqlalchemy import create_engine, text
    from odf.observability import _instrument_sql
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    engine = create_engine("sqlite://")
    _instrument_sql(engine, provider.get_tracer("test"))
    with engine.connect() as c:
        assert c.execute(text("select 1")).scalar() == 1
    spans = exporter.get_finished_spans()
    assert any(s.name == "db.query" and
               s.attributes.get("db.system") == "sqlite" for s in spans)
