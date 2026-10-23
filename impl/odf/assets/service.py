import secrets

from odf.models import Asset, AssetVersion


def _next_version(session, asset_id):
    last = (session.query(AssetVersion).filter_by(asset_id=asset_id)
            .order_by(AssetVersion.version.desc()).first())
    return (last.version + 1) if last else 1


def create_asset(session, project_id, type, name, content, owner, key=None,
                 enabled=True):
    key = key or "%s_%s" % (type, secrets.token_hex(4))
    a = Asset(project_id=project_id, type=type, key=key, name=name,
              owner=owner, enabled=enabled)
    session.add(a)
    session.flush()
    v = AssetVersion(asset_id=a.id, version=1, content_json=content,
                     status="draft", created_by=owner)
    session.add(v)
    session.flush()
    a.draft_version_id = v.id
    session.commit()
    session.refresh(a)
    return a


def get_asset(session, asset_id):
    return session.get(Asset, asset_id)


def list_assets(session, project_id, type=None):
    q = session.query(Asset).filter_by(project_id=project_id)
    if type:
        q = q.filter_by(type=type)
    return q.order_by(Asset.id).all()


def update_draft(session, asset_id, content, actor, note=""):
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    v = AssetVersion(asset_id=asset_id, version=_next_version(session, asset_id),
                     content_json=content, status="draft",
                     created_by=actor, note=note)
    session.add(v)
    session.flush()
    a.draft_version_id = v.id
    session.commit()
    session.refresh(v)
    return v


def _validate_for(session, asset, content):
    if asset.type == "pipeline":
        from odf.pipeline.validate import validate_pipeline_content
        return validate_pipeline_content(session, content, asset.project_id)
    if asset.type == "api":
        from odf.apistudio.content import validate_content
        return validate_content(session, content, asset.project_id)
    if asset.type == "dataset":
        from odf.modelstudio.content import validate_dataset
        return validate_dataset(session, content, asset.project_id)
    if asset.type == "metric":
        from odf.modelstudio.content import validate_metric
        return validate_metric(session, content, asset.project_id)
    if asset.type == "dashboard":
        from odf.dashboards.content import validate_dashboard
        return validate_dashboard(session, content, asset.project_id)
    if asset.type == "app":
        from odf.appstudio.content import validate_app
        return validate_app(session, content, asset.project_id)
    return []


def publish_asset(session, asset_id, actor):
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    v = session.get(AssetVersion, a.draft_version_id) if a.draft_version_id else None
    if not v:
        raise ValueError("draft not found")
    errs = _validate_for(session, a, v.content_json)
    if errs:
        raise ValueError("invalid content: %s" % errs)
    if a.published_version_id:
        old = session.get(AssetVersion, a.published_version_id)
        if old:
            old.status = "archived"
    v.status = "published"
    a.published_version_id = v.id
    if a.type == "api":
        a.enabled = True
    if a.type == "pipeline":
        from odf.pipeline.lineage import record_lineage
        record_lineage(session, a, v.content_json)
    session.commit()
    session.refresh(v)
    from odf.webhooks.service import emit_safe
    emit_safe(session, a.project_id, "asset.published",
              {"asset_id": a.id, "type": a.type, "key": a.key,
               "name": a.name, "version": v.version})
    return v


def rollback_asset(session, asset_id, version, actor):
    a = session.get(Asset, asset_id)
    old = (session.query(AssetVersion)
           .filter_by(asset_id=asset_id, version=version).first())
    if not a or not old:
        raise ValueError("version not found")
    if old.status == "draft":
        raise ValueError("cannot rollback to a draft version")
    if a.type == "pipeline":
        from odf.pipeline.schema import validate_dag
        errs = validate_dag(old.content_json)
    else:
        errs = _validate_for(session, a, old.content_json)
    if errs:
        raise ValueError("invalid content: %s" % errs)
    if a.published_version_id:
        current = session.get(AssetVersion, a.published_version_id)
        if current:
            current.status = "archived"
    v = AssetVersion(asset_id=asset_id, version=_next_version(session, asset_id),
                     content_json=old.content_json, status="published",
                     created_by=actor, note="rollback to %s" % version)
    session.add(v)
    session.flush()
    a.published_version_id = v.id
    if a.type == "api":
        a.enabled = True
    if a.type == "pipeline":
        from odf.pipeline.lineage import record_lineage
        record_lineage(session, a, old.content_json)
    session.commit()
    session.refresh(v)
    from odf.webhooks.service import emit_safe
    emit_safe(session, a.project_id, "asset.rolled_back",
              {"asset_id": a.id, "type": a.type, "key": a.key,
               "name": a.name, "version": v.version})
    return v


def update_asset(session, asset_id, name=None, cron=None):
    a = session.get(Asset, asset_id)
    if not a:
        raise ValueError("asset not found")
    if name is not None:
        a.name = name
    if cron is not None:
        a.cron = cron or None
    session.commit()
    session.refresh(a)
    return a


def list_versions(session, asset_id):
    return (session.query(AssetVersion).filter_by(asset_id=asset_id)
            .order_by(AssetVersion.version.desc()).all())


def get_version(session, asset_id, version):
    return (session.query(AssetVersion)
            .filter_by(asset_id=asset_id, version=version).first())
