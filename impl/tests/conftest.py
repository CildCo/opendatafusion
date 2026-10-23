import pytest

from odf.db import Base, SessionLocal, engine
from odf.models import Project
from odf.settings import get_settings


@pytest.fixture(scope="session", autouse=True)
def _test_schema():
    url = get_settings().database_url
    if not (url.startswith("sqlite") or "test" in url):
        pytest.exit("refusing to create schema on a non-test database",
                    returncode=2)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        if not s.get(Project, 1):
            s.add(Project(id=1, code="default", name="Default", status=1))
            s.commit()
    yield
