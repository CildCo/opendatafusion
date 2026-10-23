import secrets

from odf.models import AkSk
from odf.services.crypto import encrypt_secret


def issue_aksk(session, project_id: int):
    ak = "ak_" + secrets.token_hex(8)
    sk = secrets.token_urlsafe(32)
    row = AkSk(project_id=project_id, ak=ak,
               sk_encrypted=encrypt_secret(sk), enabled=True)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row, sk


def list_aksk(session, project_id: int):
    return (session.query(AkSk).filter_by(project_id=project_id)
            .order_by(AkSk.id).all())


def revoke_aksk(session, ak: str) -> AkSk:
    row = session.query(AkSk).filter_by(ak=ak).first()
    if not row:
        raise ValueError("ak not found")
    row.enabled = False
    session.commit()
    return row
