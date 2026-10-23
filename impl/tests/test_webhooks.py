import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Project, WebhookDelivery
from odf.webhooks import service


def _env():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add_all([Project(id=1, code="w1", name="w1", status=1),
               Project(id=2, code="w2", name="w2", status=1)])
    s.commit()
    return s


@pytest.fixture(autouse=True)
def _allow_private(monkeypatch):
    monkeypatch.setattr(
        service, "get_settings",
        lambda: SimpleNamespace(webhook_allow_private=True,
                                webhook_max_payload=65536))


def test_validate_url_and_secret_storage():
    assert service.validate_url("http://127.0.0.1:9/h", True)
    with pytest.raises(ValueError):
        service.validate_url("http://127.0.0.1:9/h", False)
    with pytest.raises(ValueError):
        service.validate_url("ftp://example.com/h", True)
    s = _env()
    out = service.create_subscription(s, 1, "hook", "http://127.0.0.1:9/h",
                                      ["asset.published"], True, "u")
    assert out["secret"]
    row = service.list_subscriptions(s, 1)[0]
    assert "secret" not in row
    assert out["secret"] not in json.dumps(row, default=str)


def test_emit_matches_events_and_scopes():
    s = _env()
    service.create_subscription(s, 1, "pub", "http://127.0.0.1:9/a",
                                ["asset.published"], True, "u")
    service.create_subscription(s, 1, "all", "http://127.0.0.1:9/b", [], True,
                                "u")
    service.create_subscription(s, 1, "off", "http://127.0.0.1:9/c", [],
                                False, "u")
    service.create_subscription(s, 2, "other", "http://127.0.0.1:9/d", [],
                                True, "u")
    service.emit(s, 1, "asset.published", {"id": 1})
    assert s.query(WebhookDelivery).count() == 2
    service.emit(s, 1, "alert.raised", {"id": 2})
    assert s.query(WebhookDelivery).count() == 3


def test_delivery_success_retry_and_failure(monkeypatch):
    s = _env()
    out = service.create_subscription(s, 1, "hook", "http://127.0.0.1:9/h",
                                      [], True, "u")
    service.emit(s, 1, "asset.published", {"id": 1})
    calls = []

    def ok(url, body, headers, allow_private=False):
        calls.append((url, body, headers))
        return 200

    monkeypatch.setattr(service, "_send", ok)
    assert service.deliver_due(s) == 1
    d = s.query(WebhookDelivery).first()
    assert d.status == "success" and d.attempts == 1
    expected = hmac.new(out["secret"].encode(), calls[0][1],
                        hashlib.sha256).hexdigest()
    assert calls[0][2]["X-ODF-Signature"] == "sha256=" + expected

    service.emit(s, 1, "asset.published", {"id": 2})
    d2 = (s.query(WebhookDelivery).filter_by(status="pending")
          .order_by(WebhookDelivery.id.desc()).first())

    monkeypatch.setattr(service, "_send", lambda *a, **k: 500)
    service.deliver_due(s)
    s.refresh(d2)
    assert d2.status == "pending" and d2.attempts == 1
    d2.attempts = 4
    d2.next_attempt_at = datetime.now(timezone.utc)
    s.commit()
    service.deliver_due(s)
    s.refresh(d2)
    assert d2.status == "failed" and d2.attempts == 5


def test_webhook_routes(monkeypatch):
    from fastapi.testclient import TestClient
    from odf.db import SessionLocal
    from odf.main import app
    from odf.models import User
    from odf.services.auth import create_token
    with SessionLocal() as s:
        u = s.get(User, 1)
        if not u:
            u = User(id=1, username="wh", password_hash="x",
                     role="admin", active=True)
            s.add(u)
        else:
            u.role = "admin"
            u.active = True
        s.commit()
    h = {"Authorization": "Bearer " + create_token(1, 1)}
    c = TestClient(app)
    r = c.post("/api/v1/webhooks",
               json={"name": "smoke", "url": "http://127.0.0.1:9/h",
                     "events": ["asset.published"]}, headers=h)
    assert r.status_code == 200
    wid = r.json()["id"]
    assert "secret" in r.json()
    listed = c.get("/api/v1/webhooks", headers=h).json()
    assert listed and "secret" not in listed[0]
    assert c.post(f"/api/v1/webhooks/{wid}/test",
                  headers=h).status_code == 200
    assert c.get(f"/api/v1/webhooks/{wid}/deliveries",
                 headers=h).status_code == 200
    assert c.get("/api/v1/webhooks/events", headers=h).status_code == 200


def test_delivery_revalidates_url(monkeypatch):
    s = _env()
    service.create_subscription(s, 1, "hook", "http://127.0.0.1:9/h", [],
                                True, "u")
    service.emit(s, 1, "asset.published", {"id": 1})
    monkeypatch.setattr(
        service, "get_settings",
        lambda: SimpleNamespace(webhook_allow_private=False,
                                webhook_max_payload=65536))
    service.deliver_due(s)
    d = s.query(WebhookDelivery).first()
    assert d.status == "failed" and "not allowed" in d.error


def test_delete_subscription_removes_deliveries():
    s = _env()
    out = service.create_subscription(s, 1, "hook", "http://127.0.0.1:9/h",
                                      [], True, "u")
    service.emit(s, 1, "asset.published", {"id": 1})
    assert s.query(WebhookDelivery).count() == 1
    service.delete_subscription(s, 1, out["id"], "u")
    assert s.query(WebhookDelivery).count() == 0


def test_bad_secret_does_not_block_delivery(monkeypatch):
    s = _env()
    out = service.create_subscription(s, 1, "hook", "http://127.0.0.1:9/h",
                                      [], True, "u")
    from odf.models import WebhookSubscription
    row = s.get(WebhookSubscription, out["id"])
    row.secret_encrypted = "not-a-fernet-token"
    s.commit()
    service.emit(s, 1, "asset.published", {"id": 1})
    monkeypatch.setattr(service, "_send", lambda *a, **k: 200)
    service.deliver_due(s)
    d = s.query(WebhookDelivery).first()
    assert d.attempts == 1 and d.status == "pending" and d.error
