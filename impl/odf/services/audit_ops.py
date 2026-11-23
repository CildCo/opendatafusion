from datetime import datetime, timedelta, timezone

from odf.models import AuditLog, PlatformSetting


def _audit_config(session):
    row = session.get(PlatformSetting, 1)
    return (row.settings_json or {}).get("audit") or {} if row else {}


def _save(session, row, config):
    doc = dict(row.settings_json or {})
    doc["audit"] = config
    row.settings_json = doc
    session.commit()


def maintenance(session, now=None):
    now = now or datetime.now(timezone.utc)
    config = _audit_config(session)
    retention = int(config.get("retention_days") or 0)
    if retention > 0:
        cutoff = now - timedelta(days=retention)
        (session.query(AuditLog).filter(AuditLog.at < cutoff)
         .delete(synchronize_session=False))
        session.commit()
    url = (config.get("siem_url") or "").strip()
    if not url:
        return
    cursor = int(config.get("siem_cursor") or 0)
    rows = (session.query(AuditLog).filter(AuditLog.id > cursor)
            .order_by(AuditLog.id).limit(200).all())
    if not rows:
        return
    import json
    from odf.services.net import request as outbound
    body = json.dumps([{
        "id": row.id, "actor": row.actor, "action": row.action,
        "target": row.target, "detail": row.detail_json,
        "at": row.at.isoformat() if row.at else None,
    } for row in rows], ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = (config.get("siem_token") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        outbound(url, method="POST", body=body, headers=headers, timeout=10)
    except Exception:
        return
    config["siem_cursor"] = rows[-1].id
    row = session.get(PlatformSetting, 1)
    if row:
        _save(session, row, config)
