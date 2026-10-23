from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .settings import get_settings

_url = get_settings().database_url
_settings = get_settings()
_args = {"connect_args": {"check_same_thread": False}}     if _url.startswith("sqlite") else {}


def _pool_kwargs(url: str, settings) -> dict:
    if url.startswith("sqlite"):
        return {}
    return {"pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_timeout": settings.db_pool_timeout,
            "pool_recycle": settings.db_pool_recycle_s,
            "pool_use_lifo": True}


engine = create_engine(_url, pool_pre_ping=True,
                       **_args, **_pool_kwargs(_url, _settings))
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session():
    with SessionLocal() as s:
        yield s
