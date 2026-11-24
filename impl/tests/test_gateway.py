from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.api.openapi_gateway import extract_auth, resolve_api_asset
from odf.db import Base
from odf.models import Asset, Project


def test_extract_auth():
    ak, sig = extract_auth("AK:sig")
    assert ak == "AK" and sig == "sig"


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_api_key_is_scoped_to_project():
    s = _session()
    s.add(Project(id=1, code="p1", name="p1", status=1))
    s.add(Project(id=2, code="p2", name="p2", status=1))
    s.add(Asset(project_id=2, type="api", key="k", name="a",
                owner="admin"))
    s.commit()
    assert resolve_api_asset(s, "p2", "k") is not None
    assert resolve_api_asset(s, "p1", "k") is None
