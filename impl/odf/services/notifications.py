from datetime import datetime, timezone

from sqlalchemy import select

from odf.models import Notification, NotificationRead


def notify(session, project_id: int, kind: str, title: str,
           body: str = "", link: str = "") -> Notification:
    row = Notification(project_id=project_id, kind=kind,
                       title=title[:200], body=body, link=link[:256])
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_for(session, project_id: int, user_id: int, limit: int = 50,
             unread_only: bool = False):
    limit = max(1, min(int(limit or 50), 200))
    rows = (session.query(Notification)
            .filter(Notification.project_id == project_id)
            .order_by(Notification.id.desc())
            .limit(limit).all())
    read_ids = {r.notification_id for r in
                session.query(NotificationRead)
                .filter(NotificationRead.user_id == user_id,
                        NotificationRead.notification_id.in_(
                            [n.id for n in rows] or [0])).all()}
    items = [{"id": n.id, "kind": n.kind, "title": n.title,
              "body": n.body, "link": n.link,
              "created_at": n.created_at.isoformat(),
              "read": n.id in read_ids}
             for n in rows]
    if unread_only:
        items = [item for item in items if not item["read"]]
    unread = (session.query(Notification)
              .filter(Notification.project_id == project_id,
                      ~Notification.id.in_(
                          select(NotificationRead.notification_id)
                          .where(NotificationRead.user_id == user_id)))
              .count())
    return {"items": items, "unread": unread}


def mark_read(session, project_id: int, user_id: int,
              notification_id: int) -> None:
    row = session.get(Notification, notification_id)
    if not row or row.project_id != project_id:
        raise ValueError("notification not found")
    existing = (session.query(NotificationRead)
                .filter_by(user_id=user_id, notification_id=notification_id)
                .first())
    if not existing:
        session.add(NotificationRead(
            user_id=user_id, notification_id=notification_id,
            read_at=datetime.now(timezone.utc)))
        session.commit()


def mark_all_read(session, project_id: int, user_id: int) -> int:
    ids = [row[0] for row in
           session.query(Notification.id)
           .filter(Notification.project_id == project_id).all()]
    if not ids:
        return 0
    read = {row[0] for row in
            session.query(NotificationRead.notification_id)
            .filter(NotificationRead.user_id == user_id,
                    NotificationRead.notification_id.in_(ids)).all()}
    added = 0
    now = datetime.now(timezone.utc)
    for notification_id in ids:
        if notification_id in read:
            continue
        session.add(NotificationRead(user_id=user_id,
                                     notification_id=notification_id,
                                     read_at=now))
        added += 1
    session.commit()
    return added
