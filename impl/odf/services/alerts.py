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


def raise_alert(session, project_id: int, severity: str, title: str,
                detail: dict | None = None, rule_id: int | None = None) -> Alert:
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
    return a


def evaluate_health(session, project_id: int, flow_id: int,
                    flow_name: str, health: dict) -> Alert | None:
    if health.get("status") in (None, "ok", "unknown"):
        return None
    severity = "critical" if health["status"] == "critical" else "warning"
    title = "flow %s: %s" % (flow_name, health["status"])
    return raise_alert(session, project_id, severity, title,
                       {"flow_id": flow_id, **health})


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
