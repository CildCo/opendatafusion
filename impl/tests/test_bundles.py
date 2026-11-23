from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from odf.assets.service import create_asset
from odf.db import Base
from odf.models import Asset, AssetVersion, Datasource, Project


def _session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(Project(id=1, code="dev", name="Dev", status=1,
                  environment="dev"))
    s.add(Project(id=2, code="prod", name="Prod", status=1,
                  environment="prod"))
    s.add(Datasource(id=1, project_id=1, name="pg", kind="sqlite",
                     dsn_encrypted="secret-dsn"))
    s.add(Datasource(id=2, project_id=2, name="pg", kind="sqlite",
                     dsn_encrypted="other-secret"))
    s.commit()
    return s


def _publish(s, project_id, content):
    asset = create_asset(s, project_id, "dashboard", "Board", content, "u")
    version = AssetVersion(asset_id=asset.id, version=2,
                           content_json=content, status="published",
                           created_by="u")
    s.add(version)
    s.flush()
    asset.published_version_id = version.id
    s.commit()
    return asset


def test_export_import_bundle_remaps_datasources():
    from odf.services.bundles import (export_bundle, import_bundle,
                                      validate_bundle)
    s = _session()
    _publish(s, 1, {"query": {"datasource_id": 1}, "widgets": []})
    bundle = export_bundle(s, 1)
    assert bundle["format"] == "odf-bundle"
    assert "secret-dsn" not in str(bundle)
    check = validate_bundle(s, 2, bundle)
    assert check["create"] == 1
    assert check["unresolved_datasources"] == []
    out = import_bundle(s, 2, bundle, "u")
    assert out["created"] == 1
    asset = s.query(Asset).filter_by(project_id=2).one()
    assert asset.published_version_id is None
    version = s.get(AssetVersion, asset.draft_version_id)
    assert version.content_json["query"]["datasource_id"] == 2
    again = import_bundle(s, 2, bundle, "u")
    assert again["updated"] == 1
    assert s.query(Asset).filter_by(project_id=2).count() == 1


def test_bundle_reports_unresolved_datasource():
    from odf.services.bundles import export_bundle, validate_bundle
    s = _session()
    _publish(s, 1, {"query": {"datasource_id": 1}, "widgets": []})
    bundle = export_bundle(s, 1)
    bundle["datasources"][0]["name"] = "missing"
    check = validate_bundle(s, 2, bundle)
    assert check["unresolved_datasources"] == ["missing (sqlite)"]


def test_bundle_remaps_asset_references():
    from odf.services.bundles import export_bundle, import_bundle
    s = _session()
    base = _publish(s, 1, {"widgets": []})
    referencing = _publish(s, 1, {"dataset_id": base.id})
    bundle = export_bundle(s, 1)
    import_bundle(s, 2, bundle, "u")
    target_base = (s.query(Asset)
                   .filter_by(project_id=2, name="Board").all())
    assert len(target_base) == 2
    imported = [s.get(AssetVersion, a.draft_version_id)
                for a in target_base]
    refs = [v.content_json.get("dataset_id") for v in imported
            if v.content_json.get("dataset_id")]
    assert refs and all(ref in {a.id for a in target_base} for ref in refs)
