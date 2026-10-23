from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.apistudio.interface_import import import_interface_records
from odf.db import Base
from odf.models import Asset, AssetVersion, Interface


def _s():
    e = create_engine("sqlite://")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_imports_published_and_draft_interfaces():
    s = _s()
    s.add(Interface(id=1, project_id=1, datasource_id=1,
                    interface_key="k1", name="published", sql_text="select 1",
                    params_json=[], output_json=[], status=1))
    s.add(Interface(id=2, project_id=1, datasource_id=1,
                    interface_key="k2", name="draft", sql_text="select 2",
                    params_json=[], output_json=[], status=0))
    s.commit()
    assert import_interface_records(s) == 2
    a1 = s.query(Asset).filter_by(key="k1").one()
    a2 = s.query(Asset).filter_by(key="k2").one()
    assert a1.type == "api" and a1.enabled is True
    assert a2.enabled is False
    v = s.get(AssetVersion, a1.published_version_id)
    assert v.content_json["mode"] == "sql"
    assert v.content_json["sql"] == "select 1"
    assert v.content_json["query"]["datasource_id"] == 1


def test_import_is_idempotent_and_skips_existing_key():
    s = _s()
    s.add(Interface(id=1, project_id=1, datasource_id=1,
                    interface_key="k1", name="published", sql_text="select 1",
                    params_json=[], output_json=[], status=1))
    s.commit()
    assert import_interface_records(s) == 1
    assert import_interface_records(s) == 0
    assert s.query(Asset).filter_by(key="k1").count() == 1
