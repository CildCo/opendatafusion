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


def set_role(session, user_id: int, role: str) -> User:
    u = session.get(User, user_id)
    if not u:
        raise ValueError("user not found")
    u.role = role
    session.commit()
    return u


def set_active(session, user_id: int, active: bool) -> User:
    u = session.get(User, user_id)
    if not u:
        raise ValueError("user not found")
    u.active = active
    session.commit()
    return u
