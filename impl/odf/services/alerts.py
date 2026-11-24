from datetime import datetime, timezone

from odf.models import Alert, AlertRule


def create_rule(session, project_id: int, name: str, kind: str,
                config: dict | None = None) -> AlertRule:
    r = AlertRule(project_id=project_id, name=name, kind=kind,
                  config_json=config or {}, enabled=True)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def list_rules(session, project_id: int):
    return (session.query(AlertRule).filter_by(project_id=project_id)
            .order_by(AlertRule.id).all())


def _muted(session, project_id: int, severity: str, title: str) -> bool:
    rules = (session.query(AlertRule)
             .filter_by(project_id=project_id, kind="mute", enabled=True)
             .all())
    for rule in rules:
        config = rule.config_json or {}
        if config.get("severity") and config["severity"] != severity:
            continue
        needle = str(config.get("title_contains") or "").lower()
        if needle and needle not in (title or "").lower():
            continue
        return True
    return False


def raise_alert(session, project_id: int, severity: str, title: str,
                detail: dict | None = None, rule_id: int | None = None):
    if _muted(session, project_id, severity, title):
        return None
    existing = (session.query(Alert)
                .filter_by(project_id=project_id, title=title, status="open")
                .first())
    if existing:
        return existing
    a = Alert(project_id=project_id, rule_id=rule_id, severity=severity,
              title=title, detail_json=detail or {}, status="open")
    session.add(a)
    session.commit()
    session.refresh(a)
    from odf.webhooks.service import emit_safe
    emit_safe(session, project_id, "alert.raised",
              {"alert_id": a.id, "severity": severity, "title": title})
    from odf.services.notifications import notify
    notify(session, project_id, "alert", "新告警：%s" % title,
           "级别：%s" % severity, "/alerts")
    _forward_webhook(session, a)
    return a


def _forward_webhook(session, alert):
    try:
        import json
        from odf.services.net import request as outbound
        from odf.services.platform import get_doc
        url = ((get_doc(session).get("alerts") or {})
               .get("webhook_url") or "").strip()
        if not url:
            return
        body = json.dumps({
            "text": "[%s] %s" % (alert.severity, alert.title),
            "alert": {"id": alert.id, "severity": alert.severity,
                      "title": alert.title, "detail": alert.detail_json},
        }).encode()
        outbound(url, "POST", body,
                 headers={"Content-Type": "application/json"},
                 timeout=5)
    except Exception:
        pass


def list_alerts(session, project_id: int, status: str | None = None):
    q = session.query(Alert).filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    return q.order_by(Alert.id.desc()).limit(200).all()


def ack_alert(session, alert_id: int) -> Alert:
    a = session.get(Alert, alert_id)
    if not a:
        raise ValueError("alert not found")
    a.status = "acked"
    a.acked_at = datetime.now(timezone.utc)
    session.commit()
    return a


def close_alert(session, alert_id: int) -> Alert:
    a = session.get(Alert, alert_id)
    if not a:
        raise ValueError("alert not found")
    a.status = "closed"
    a.closed_at = datetime.now(timezone.utc)
    session.commit()
    return a


def delete_rule(session, project_id: int, rule_id: int) -> None:
    rule = session.get(AlertRule, rule_id)
    if not rule or rule.project_id != project_id:
        raise ValueError("rule not found")
    session.delete(rule)
    session.commit()
