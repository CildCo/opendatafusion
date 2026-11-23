from datetime import datetime, timezone

import bcrypt

from odf.models import User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_user(session, username: str, password: str, role: str = "viewer",
                active: bool = True) -> User:
    u = User(username=username, password_hash=hash_password(password),
             role=role, active=active)
    session.add(u)
    session.commit()
    session.refresh(u)
    return u


def authenticate(session, username: str, password: str):
    u = session.query(User).filter_by(username=username, active=True).first()
    if u and verify_password(password, u.password_hash):
        return u
    return None


def list_users(session):
    return session.query(User).order_by(User.id).all()


def _other_active_admins(session, user_id: int) -> int:
    return (session.query(User)
            .filter(User.id != user_id, User.role == "admin",
                    User.active.is_(True))
            .count())


def set_role(session, user_id: int, role: str,
             actor_id: int | None = None) -> User:
    u = session.get(User, user_id)
    if not u:
        raise ValueError("user not found")
    if actor_id is not None and u.id == actor_id and role != u.role:
        raise ValueError("you cannot change your own role")
    if (u.role == "admin" and role != "admin" and u.active
            and _other_active_admins(session, u.id) == 0):
        raise ValueError("at least one active administrator is required")
    u.role = role
    session.commit()
    return u


def set_active(session, user_id: int, active: bool,
               actor_id: int | None = None) -> User:
    u = session.get(User, user_id)
    if not u:
        raise ValueError("user not found")
    if not active and actor_id is not None and u.id == actor_id:
        raise ValueError("you cannot deactivate your own account")
    if (not active and u.role == "admin" and u.active
            and _other_active_admins(session, u.id) == 0):
        raise ValueError("at least one active administrator is required")
    u.active = active
    session.commit()
    return u


def set_active_by_name(session, username: str, active: bool) -> User:
    """Break-glass helper for the CLI; bypasses the policy guards."""
    u = session.query(User).filter_by(username=username).first()
    if not u:
        raise ValueError("user not found")
    u.active = active
    session.commit()
    return u


def reset_password_by_name(session, username: str, password: str) -> User:
    """Break-glass helper for the CLI; revokes existing sessions."""
    u = session.query(User).filter_by(username=username).first()
    if not u:
        raise ValueError("user not found")
    u.password_hash = hash_password(password)
    u.password_changed_at = datetime.now(timezone.utc)
    u.token_version = int(u.token_version or 0) + 1
    session.commit()
    return u


def set_platform_admin(session, user_id: int, value: bool,
                       actor_id: int | None = None) -> User:
    u = session.get(User, user_id)
    if not u:
        raise ValueError("user not found")
    if actor_id is not None and u.id == actor_id:
        raise ValueError("you cannot change your own platform role")
    if not value and is_platform_admin(u):
        others = (session.query(User)
                  .filter(User.id != u.id,
                          (User.platform_admin.is_(True))
                          | (User.role == "admin"))
                  .count())
        if others == 0:
            raise ValueError("at least one platform administrator is required")
    u.platform_admin = value
    session.commit()
    return u


def is_platform_admin(user) -> bool:
    return bool(user and (getattr(user, "platform_admin", False)
                          or user.role == "admin"))


def reset_totp_by_name(session, username: str) -> User:
    """Break-glass helper for a lost authenticator device."""
    u = session.query(User).filter_by(username=username).first()
    if not u:
        raise ValueError("user not found")
    u.totp_secret_encrypted = None
    u.totp_enabled = False
    u.totp_last_step = None
    session.commit()
    return u
