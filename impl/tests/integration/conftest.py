import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.db import Base
from odf.models import Project


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip("%s is not configured" % name)
    return value


def has_env(name: str) -> bool:
    return bool(os.environ.get(name))


@pytest.fixture()
def control():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    session.add(Project(id=1, code="it", name="integration", status=1))
    session.commit()
    yield session
    session.close()
