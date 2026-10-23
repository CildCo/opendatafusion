from cryptography.fernet import Fernet

from odf.models import AkSk, Datasource, User, WebhookSubscription
from odf.services.aksk_admin import issue_aksk
from odf.webhooks.service import update_subscription


def rotate_fernet(session, old_key, new_key):
    old = Fernet(old_key.encode())
    new = Fernet(new_key.encode())
    counts = {"datasources": 0, "aksk": 0, "webhooks": 0, "totp": 0}
    for ds in session.query(Datasource).all():
        ds.dsn_encrypted = new.encrypt(
            old.decrypt(ds.dsn_encrypted.encode())).decode()
        counts["datasources"] += 1
    for row in session.query(AkSk).all():
        row.sk_encrypted = new.encrypt(
            old.decrypt(row.sk_encrypted.encode())).decode()
        counts["aksk"] += 1
    for wh in session.query(WebhookSubscription).all():
        wh.secret_encrypted = new.encrypt(
            old.decrypt(wh.secret_encrypted.encode())).decode()
        counts["webhooks"] += 1
    for user in session.query(User).filter(
            User.totp_secret_encrypted.isnot(None)).all():
        user.totp_secret_encrypted = new.encrypt(
            old.decrypt(user.totp_secret_encrypted.encode())).decode()
        counts["totp"] += 1
    session.commit()
    return counts


def rotate_aksk(session, project_id):
    for row in session.query(AkSk).filter_by(project_id=project_id).all():
        row.enabled = False
    session.commit()
    row, sk = issue_aksk(session, project_id)
    return {"ak": row.ak, "sk": sk}


def rotate_webhook(session, project_id, webhook_id, actor="cli"):
    out = update_subscription(session, project_id, webhook_id,
                             {"rotate_secret": True}, actor)
    return {"id": out["id"], "secret": out.get("secret")}
