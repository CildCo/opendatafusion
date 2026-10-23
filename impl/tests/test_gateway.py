import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.api.openapi_gateway import extract_auth, resolve_access
from odf.db import Base
from odf.models import AkSk, Interface, Project
from odf.services.crypto import encrypt_secret


def test_extract_auth():
    ak, sig = extract_auth("AK:sig")
    assert ak == "AK" and sig == "sig"


def _session():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_project_key_must_match_ak_project():
    s = _session()
    s.add(Project(id=1, code="p1", name="p1", status=1))
    s.add(Project(id=2, code="p2", name="p2", status=1))
    s.add(AkSk(project_id=1, ak="ak1", sk_encrypted=encrypt_secret("sk")))
    s.add(Interface(project_id=2, datasource_id=1, interface_key="k",
                    name="i", sql_text="select 1", params_json=[],
                    output_json=[], status=1))
    s.commit()
    with pytest.raises(HTTPException) as e:
        resolve_access(s, "ak1", "p2", "k")
    assert e.value.status_code == 403
