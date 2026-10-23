import hashlib
import hmac
import json
import secrets
import socket
import ssl
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from odf.models import WebhookDelivery, WebhookSubscription
from odf.services.audit import write_audit
from odf.services.crypto import decrypt_secret, encrypt_secret
from odf.settings import get_settings

EVENTS = {"asset.published", "asset.rolled_back", "job.failed",
          "alert.raised", "app.submitted", "webhook.test"}
MAX_ATTEMPTS = 5


def _now():
    return datetime.now(timezone.utc)


def _aware(dt):
    return dt if dt and dt.tzinfo else (
        dt.replace(tzinfo=timezone.utc) if dt else None)


def resolve_public_url(url, allow_private=False):
    from odf.services.net import resolve_public_url as _resolve
    return _resolve(url, allow_private, label="webhook")


def validate_url(url, allow_private=False):
    resolve_public_url(url, allow_private)
    return True


def _send(url, body, headers, allow_private=False):
    parts, port, ip = resolve_public_url(url, allow_private)
    sock = socket.create_connection((ip, port), timeout=5)
    try:
        if parts.scheme == "https":
            sock = ssl.create_default_context().wrap_socket(
                sock, server_hostname=parts.hostname)
        path = parts.path or "/"
        if parts.query:
            path += "?" + parts.query
        lines = ["POST %s HTTP/1.1" % path,
                 "Host: %s" % parts.netloc, "Connection: close"]
        lines.extend("%s: %s" % (k, v) for k, v in headers.items())
        lines.extend(["Content-Length: %d" % len(body), "", ""])
        sock.sendall("\r\n".join(lines).encode() + body)
        data = b""
        while len(data) < 65536:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
        status = data.split(b"\r\n", 1)[0].split()
        if len(status) < 2:
            raise ValueError("invalid webhook response")
        return int(status[1])
    finally:
        sock.close()


def _events(value):
    if value is None:
        return []
    if not isinstance(value, list) or \
            any(not isinstance(e, str) or e not in EVENTS for e in value):
        raise ValueError("invalid webhook events")
    return list(dict.fromkeys(value))


def _sub_dict(s, include_secret=False):
    out = {"id": s.id, "name": s.name, "url": s.url,
           "events": s.events_json or [], "enabled": s.enabled,
           "created_by": s.created_by, "created_at": s.created_at,
           "last_status": s.last_status,
           "last_attempt_at": s.last_attempt_at,
           "failure_count": s.failure_count, "has_secret": True}
    if include_secret:
        out["secret"] = include_secret
    return out


def _subscription(session, project_id, sub_id):
    s = session.get(WebhookSubscription, sub_id)
    if not s or s.project_id != project_id:
        raise ValueError("webhook not found")
    return s


def create_subscription(session, project_id, name, url, events, enabled,
                        actor, secret=None):
    validate_url(url, get_settings().webhook_allow_private)
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 128:
        raise ValueError("invalid webhook name")
    events = _events(events)
    raw_secret = secret or secrets.token_urlsafe(24)
    if not isinstance(raw_secret, str) or not 8 <= len(raw_secret) <= 128:
        raise ValueError("invalid webhook secret")
    s = WebhookSubscription(project_id=project_id, name=name.strip(),
                            url=url, secret_encrypted=encrypt_secret(
                                raw_secret),
                            events_json=events, enabled=bool(enabled),
                            created_by=actor)
    session.add(s)
    session.commit()
    session.refresh(s)
    write_audit(session, actor, "create_webhook", str(s.id),
                {"name": s.name, "events": events})
    return _sub_dict(s, raw_secret)


def list_subscriptions(session, project_id):
    return [_sub_dict(s) for s in
            session.query(WebhookSubscription)
            .filter_by(project_id=project_id)
            .order_by(WebhookSubscription.id.desc()).all()]


def update_subscription(session, project_id, sub_id, fields, actor):
    s = _subscription(session, project_id, sub_id)
    if "name" in fields:
        if not isinstance(fields["name"], str) or \
                not 1 <= len(fields["name"].strip()) <= 128:
            raise ValueError("invalid webhook name")
        s.name = fields["name"].strip()
    if "url" in fields:
        validate_url(fields["url"],
                     get_settings().webhook_allow_private)
        s.url = fields["url"]
    if "events" in fields:
        s.events_json = _events(fields["events"])
    if "enabled" in fields:
        s.enabled = bool(fields["enabled"])
    rotated = None
    if fields.get("rotate_secret"):
        rotated = secrets.token_urlsafe(24)
        s.secret_encrypted = encrypt_secret(rotated)
    session.commit()
    write_audit(session, actor, "update_webhook", str(s.id), {})
    return _sub_dict(s, rotated)


def delete_subscription(session, project_id, sub_id, actor):
    s = _subscription(session, project_id, sub_id)
    session.query(WebhookDelivery).filter_by(
        subscription_id=sub_id).delete(synchronize_session=False)
    session.delete(s)
    session.commit()
    write_audit(session, actor, "delete_webhook", str(sub_id), {})


def emit(session, project_id, event, payload):
    if event not in EVENTS or event == "webhook.test":
        raise ValueError("unsupported event")
    payload = payload or {}
    body = json.dumps(payload, ensure_ascii=False, default=str)
    if len(body.encode("utf-8")) > get_settings().webhook_max_payload:
        raise ValueError("webhook payload too large")
    subs = (session.query(WebhookSubscription)
            .filter_by(project_id=project_id, enabled=True).all())
    count = 0
    for s in subs:
        if s.events_json and event not in s.events_json:
            continue
        session.add(WebhookDelivery(
            subscription_id=s.id, project_id=project_id, event=event,
            payload_json=payload, status="pending", attempts=0,
            max_attempts=MAX_ATTEMPTS, next_attempt_at=_now()))
        count += 1
    if count:
        session.commit()
    return count


def emit_safe(session, project_id, event, payload):
    try:
        return emit(session, project_id, event, payload)
    except Exception:
        return 0


def queue_test(session, project_id, sub_id, actor):
    _subscription(session, project_id, sub_id)
    session.add(WebhookDelivery(
        subscription_id=sub_id, project_id=project_id, event="webhook.test",
        payload_json={"message": "OpenDataFusion webhook test"},
        status="pending", attempts=0, max_attempts=MAX_ATTEMPTS,
        next_attempt_at=_now()))
    session.commit()
    write_audit(session, actor, "test_webhook", str(sub_id), {})
    return {"queued": True}


def list_deliveries(session, project_id, sub_id):
    _subscription(session, project_id, sub_id)
    return [{"id": d.id, "event": d.event, "status": d.status,
             "attempts": d.attempts, "response_status": d.response_status,
             "error": d.error, "created_at": d.created_at,
             "delivered_at": d.delivered_at}
            for d in (session.query(WebhookDelivery)
                      .filter_by(subscription_id=sub_id)
                      .order_by(WebhookDelivery.id.desc()).limit(100).all())]


def _sign(secret, body):
    return "sha256=" + hmac.new(secret.encode(), body,
                                hashlib.sha256).hexdigest()


def deliver_due(session, now=None, limit=20, budget_s=10):
    now = now or _now()
    deadline = _now().timestamp() + budget_s
    rows = (session.query(WebhookDelivery)
            .filter(WebhookDelivery.status == "pending",
                    WebhookDelivery.next_attempt_at <= now)
            .order_by(WebhookDelivery.id).limit(limit).all())
    count = 0
    for d in rows:
        if _now().timestamp() > deadline:
            break
        sub = session.get(WebhookSubscription, d.subscription_id)
        if not sub or not sub.enabled:
            d.status = "failed"
            d.error = "subscription disabled"
            session.commit()
            continue
        try:
            validate_url(sub.url, get_settings().webhook_allow_private)
        except ValueError as e:
            d.status = "failed"
            d.error = str(e)
            session.commit()
            continue
        try:
            body = json.dumps(d.payload_json, ensure_ascii=False,
                              default=str,
                              separators=(",", ":")).encode()
            headers = {"Content-Type": "application/json",
                       "X-ODF-Event": d.event,
                       "X-ODF-Delivery": str(d.id),
                       "X-ODF-Signature": _sign(decrypt_secret(
                           sub.secret_encrypted), body)}
            status = _send(sub.url, body, headers,
                           get_settings().webhook_allow_private)
            ok = 200 <= status < 300
            error = None if ok else "HTTP %s" % status
        except Exception as e:
            status = None
            ok = False
            error = (str(e) or e.__class__.__name__)[:300]
        sub.last_attempt_at = now
        d.attempts += 1
        d.response_status = status
        d.error = error
        if ok:
            d.status = "success"
            d.delivered_at = now
            sub.last_status = "success"
            sub.failure_count = 0
        else:
            sub.last_status = "failed"
            sub.failure_count += 1
            if d.attempts >= d.max_attempts:
                d.status = "failed"
            else:
                d.next_attempt_at = now + timedelta(
                    seconds=min(3600, 30 * 2 ** (d.attempts - 1)))
        session.commit()
        from odf.api.metrics import inc
        inc("webhook_deliveries_total",
            status="success" if ok else "failure")
        count += 1
    return count
