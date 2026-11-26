from datetime import datetime, timezone

from odf.models import (Alert, AlertNote, AlertRule, ProjectMember,
                        User)


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


def _alert(session, project_id, alert_id):
    a = session.get(Alert, alert_id)
    if not a or a.project_id != project_id:
        raise ValueError("alert not found")
    return a


def alert_assignees(session, project_id: int):
    rows = (session.query(User.username)
            .join(ProjectMember, ProjectMember.user_id == User.id)
            .filter(ProjectMember.project_id == project_id,
                    User.active.is_(True))
            .order_by(User.username).all())
    return [row[0] for row in rows]


def assign_alert(session, project_id: int, alert_id: int, assignee: str,
                 actor: str):
    a = _alert(session, project_id, alert_id)
    value = (assignee or "").strip()
    if value:
        user = session.query(User).filter_by(username=value).first()
        member = (session.query(ProjectMember)
                  .filter_by(project_id=project_id,
                             user_id=user.id).first()) if user else None
        if not user or not user.active or not member:
            raise ValueError("assignee is not an active project member")
    a.assigned_to = value or None
    session.commit()
    session.refresh(a)
    from odf.services.audit import write_audit
    write_audit(session, actor, "assign_alert", str(a.id),
                {"assigned_to": a.assigned_to or ""})
    return a


def list_alert_notes(session, project_id: int, alert_id: int):
    _alert(session, project_id, alert_id)
    return (session.query(AlertNote)
            .filter_by(project_id=project_id, alert_id=alert_id)
            .order_by(AlertNote.created_at, AlertNote.id).all())


def add_alert_note(session, project_id: int, alert_id: int, actor: str,
                   body: str):
    _alert(session, project_id, alert_id)
    text = (body or "").strip()
    if not text:
        raise ValueError("note body is required")
    if len(text) > 4000:
        raise ValueError("note body is too long")
    row = AlertNote(project_id=project_id, alert_id=alert_id, actor=actor,
                    body=text)
    session.add(row)
    session.commit()
    session.refresh(row)
    from odf.services.audit import write_audit
    write_audit(session, actor, "note_alert", str(alert_id),
                {"note_id": row.id})
    return row


def alert_notes_dict(rows):
    return [{"id": n.id, "actor": n.actor, "body": n.body,
             "created_at": n.created_at.isoformat()} for n in rows]
