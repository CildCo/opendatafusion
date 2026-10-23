from odf.models import Asset, AssetVersion


def test_asset_defaults():
    a = Asset(project_id=1, type="pipeline", key="p1", name="P1",
              owner="admin")
    assert a.enabled is True


def test_asset_version_defaults():
    v = AssetVersion(asset_id=1, version=1, content_json={"nodes": []},
                     status="draft", created_by="admin")
    assert v.status == "draft"
