import json
from datetime import datetime

from odf.models import AuditLog


def write_audit(session, actor: str, action: str, target: str, detail: dict) -> None:
    session.add(AuditLog(actor=actor, action=action, target=target,
                         detail_json=detail))
    session.commit()


def export_audit(session, before: datetime, path: str) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as fh:
        for row in (session.query(AuditLog)
                    .filter(AuditLog.at < before)
                    .order_by(AuditLog.id).yield_per(1000)):
            fh.write(json.dumps({
                "id": row.id, "actor": row.actor, "action": row.action,
                "target": row.target, "detail": row.detail_json,
                "at": row.at.isoformat() if row.at else None,
            }, ensure_ascii=False, default=str) + "\n")
            count += 1
    return count


def prune_audit(session, before: datetime, batch_size: int = 1000) -> int:
    total = 0
    while True:
        ids = [r[0] for r in (session.query(AuditLog.id)
                              .filter(AuditLog.at < before)
                              .order_by(AuditLog.id)
                              .limit(batch_size).all())]
        if not ids:
            break
        session.query(AuditLog).filter(AuditLog.id.in_(ids)).delete(
            synchronize_session=False)
        session.commit()
        total += len(ids)
    return total


def list_audit(session, limit: int = 100):
    from odf.models import User
    rows = (session.query(AuditLog).order_by(AuditLog.id.desc())
            .limit(min(int(limit or 100), 500)).all())
    ids = {int(r.actor) for r in rows if (r.actor or "").isdigit()}
    names = {}
    if ids:
        names = {u.id: u.username for u in
                 session.query(User).filter(User.id.in_(ids)).all()}
    out = []
    for r in rows:
        actor = r.actor
        if (actor or "").isdigit():
            actor = names.get(int(actor), actor)
        out.append({"id": r.id, "actor": actor, "action": r.action,
                    "target": r.target, "detail": r.detail_json,
                    "at": r.at.isoformat()})
    return out
